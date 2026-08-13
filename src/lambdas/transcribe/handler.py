import os
import uuid
import time
import threading
import azure.cognitiveservices.speech as speechsdk
from typing import Dict, Any
from dotenv import load_dotenv

from src.utils.logger import get_logger
from src.utils.retry import exponential_backoff
from src.lambdas.models.events import TranscriptionResponse

# Load environment variables
load_dotenv()

logger = get_logger(__name__, component="L2-TRANSCRIBE")

class TranscriptionError(Exception):
    """Custom exception for transcription failures."""
    pass

@exponential_backoff(
    max_retries=3,
    exceptions=(TranscriptionError, Exception),
    initial_delay=2.0
)
def transcribe_audio(audio_path: str) -> str:
    """
    Transcribes audio file using Azure Speech Services with continuous recognition.
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    speech_key = os.getenv("AZURE_SPEECH_KEY")
    speech_region = os.getenv("AZURE_SPEECH_REGION")

    if not speech_key or not speech_region:
        raise TranscriptionError("Azure Speech credentials not configured in environment.")

    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
    audio_config = speechsdk.audio.AudioConfig(filename=audio_path)
    
    # Using continuous recognition for files longer than 30 seconds
    speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

    done = False
    transcript_parts = []

    def stop_cb(evt):
        """callback that signals to stop continuous recognition upon receiving an event `evt`"""
        logger.info(f"CLOSING on {evt}")
        nonlocal done
        done = True

    def recognized_cb(evt):
        """callback for recognized text"""
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            transcript_parts.append(evt.result.text)
            logger.debug(f"RECOGNIZED: {evt.result.text}")

    def canceled_cb(evt):
        """callback for cancelled recognition"""
        if evt.result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = evt.result.cancellation_details
            logger.warning(f"CANCELED: Reason={cancellation_details.reason}")
            if cancellation_details.reason == speechsdk.CancellationReason.Error:
                logger.error(f"CANCELED: ErrorDetails={cancellation_details.error_details}")
                # We raise error only if it's an actual service error, not just end of file
                if "Authentication" in cancellation_details.error_details:
                     raise TranscriptionError(f"Azure Authentication Error: {cancellation_details.error_details}")

    # Connect callbacks to the events fired by the speech recognizer
    speech_recognizer.recognized.connect(recognized_cb)
    speech_recognizer.session_stopped.connect(stop_cb)
    speech_recognizer.canceled.connect(stop_cb)
    speech_recognizer.canceled.connect(canceled_cb)

    # Start continuous speech recognition
    logger.info(f"Starting transcription for: {audio_path}")
    speech_recognizer.start_continuous_recognition()
    
    while not done:
        time.sleep(.5)

    speech_recognizer.stop_continuous_recognition()
    
    final_transcript = " ".join(transcript_parts).strip()
    
    if not final_transcript:
        logger.error(f"Transcription resulted in empty text for {audio_path}")
        raise TranscriptionError("Transcription returned empty result.")

    return final_transcript

def handler(audio_path: str) -> Dict[str, Any]:
    """
    L2 Lambda Handler: Orchestrates audio transcription.
    """
    meeting_id = str(uuid.uuid4())
    logger.info(f"Processing meeting_id: {meeting_id}", {"audio_path": audio_path})

    try:
        transcript = transcribe_audio(audio_path)
        
        response = TranscriptionResponse(
            meeting_id=meeting_id,
            transcript=transcript,
            word_count=len(transcript.split()),
            status="transcribed"
        )
        
        logger.info("Transcription completed successfully", {
            "meeting_id": meeting_id,
            "word_count": response.word_count
        })
        
        return response.model_dump()

    except Exception as e:
        logger.error(f"Failed to process transcription for {meeting_id}: {str(e)}")
        raise
