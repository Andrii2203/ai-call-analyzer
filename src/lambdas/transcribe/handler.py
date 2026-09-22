import os
import threading
from typing import Any, Dict, List

import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv

from src.lambdas.models.events import TranscriptionResponse
from src.utils.audio import load_pcm16_mono, meeting_id_for
from src.utils.logger import get_logger
from src.utils.retry import exponential_backoff

# Load environment variables
load_dotenv()

logger = get_logger(__name__, component="L2-TRANSCRIBE")

# Azure cancellation codes worth retrying: network, throttling, temporary service faults.
# Everything else (bad key, forbidden, bad request) fails immediately.
TRANSIENT_CANCELLATION_CODES = {
    speechsdk.CancellationErrorCode.ConnectionFailure,
    speechsdk.CancellationErrorCode.ServiceTimeout,
    speechsdk.CancellationErrorCode.ServiceError,
    speechsdk.CancellationErrorCode.ServiceUnavailable,
    speechsdk.CancellationErrorCode.TooManyRequests,
}


class TranscriptionError(Exception):
    """Transcription failed and retrying will not help."""


class TransientTranscriptionError(TranscriptionError):
    """Transcription failed for a temporary reason; safe to retry."""


def _wait_timeout_sec(duration_sec: float) -> float:
    """Upper bound for one recognition session: generous, but never infinite."""
    return 60.0 + 2.0 * duration_sec


@exponential_backoff(
    max_retries=3,
    exceptions=(TransientTranscriptionError,),
    initial_delay=2.0
)
def transcribe_audio(audio_path: str) -> str:
    """
    Transcribes an audio file (MP3, WAV, FLAC, OGG) using Azure Speech continuous recognition.
    """
    audio = load_pcm16_mono(audio_path)

    speech_key = os.getenv("AZURE_SPEECH_KEY")
    speech_region = os.getenv("AZURE_SPEECH_REGION")

    if not speech_key or not speech_region:
        raise TranscriptionError("Azure Speech credentials not configured in environment.")

    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
    speech_config.speech_recognition_language = os.getenv("AZURE_SPEECH_LANGUAGE", "en-US")

    # Decoded PCM goes in through a push stream: the SDK itself reads only WAV files.
    stream = speechsdk.audio.PushAudioInputStream()
    stream.write(audio.pcm)
    stream.close()
    audio_config = speechsdk.audio.AudioConfig(stream=stream)

    # Using continuous recognition for files longer than 30 seconds
    speech_recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config, audio_config=audio_config
    )

    done = threading.Event()
    transcript_parts: List[str] = []
    errors: List[speechsdk.CancellationDetails] = []

    def stop_cb(evt):
        """callback that signals to stop continuous recognition upon receiving an event `evt`"""
        logger.info(f"CLOSING on {evt}")
        done.set()

    def recognized_cb(evt):
        """callback for recognized text"""
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            transcript_parts.append(evt.result.text)
            logger.debug(f"RECOGNIZED: {evt.result.text}")

    def canceled_cb(evt):
        """
        callback for cancelled recognition. Raising here would be lost inside the SDK thread,
        so the error is recorded and raised from the caller's thread below.
        """
        details = evt.cancellation_details
        logger.warning(f"CANCELED: Reason={details.reason}")
        if details.reason == speechsdk.CancellationReason.Error:
            logger.error(f"CANCELED: ErrorCode={details.code} ErrorDetails={details.error_details}")
            errors.append(details)
        done.set()

    # Connect callbacks to the events fired by the speech recognizer
    speech_recognizer.recognized.connect(recognized_cb)
    speech_recognizer.session_stopped.connect(stop_cb)
    speech_recognizer.canceled.connect(canceled_cb)

    # Start continuous speech recognition
    timeout_sec = _wait_timeout_sec(audio.duration_sec)
    logger.info(
        f"Starting transcription for: {audio_path}",
        {"duration_sec": round(audio.duration_sec, 2), "timeout_sec": timeout_sec},
    )
    speech_recognizer.start_continuous_recognition()
    finished = done.wait(timeout=timeout_sec)
    speech_recognizer.stop_continuous_recognition()

    if not finished:
        raise TransientTranscriptionError(
            f"Azure Speech did not finish within {timeout_sec:.0f}s for {audio_path}"
        )

    if errors:
        details = errors[0]
        message = f"Azure Speech error {details.code}: {details.error_details}"
        if details.code in TRANSIENT_CANCELLATION_CODES:
            raise TransientTranscriptionError(message)
        raise TranscriptionError(message)

    final_transcript = " ".join(transcript_parts).strip()

    if not final_transcript:
        logger.error(f"Transcription resulted in empty text for {audio_path}")
        raise TranscriptionError("Transcription returned empty result (no speech recognized).")

    return final_transcript


def handler(audio_path: str) -> Dict[str, Any]:
    """
    L2 Lambda Handler: Orchestrates audio transcription.
    """
    meeting_id = meeting_id_for(audio_path)
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

        return response.model_dump(mode="json")

    except Exception as e:
        logger.error(f"Failed to process transcription for {meeting_id}: {str(e)}")
        raise
