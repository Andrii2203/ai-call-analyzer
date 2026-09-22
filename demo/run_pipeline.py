import argparse
import os
import sys
from typing import Any, Dict

from dotenv import load_dotenv

from src.lambdas.score.handler import handler as score_handler
from src.lambdas.transcribe.handler import handler as transcribe_handler
from src.utils.audio import meeting_id_for
from src.utils.logger import get_logger
from src.utils.s3_utils import download_json_from_s3, upload_json_to_s3

# Load environment variables
load_dotenv()

logger = get_logger(__name__, component="DEMO-PIPELINE")

def run_full_pipeline(audio_path: str) -> Dict[str, Any]:
    """
    Orchestrates the full pipeline: Transcription -> Scoring -> Storage.
    The same recording always maps to the same meeting_id, so a repeated run reuses
    the stored transcript (no Azure call) and the stored score (no Groq call).
    """
    logger.info(f"--- Starting Pipeline for {audio_path} ---")

    meeting_id = meeting_id_for(audio_path)
    bucket_name = os.getenv("S3_BUCKET_NAME", "sales-score-dev")
    transcript_s3_key = f"transcripts/raw/{meeting_id}/transcript.json"

    # STEP 1: Transcription (L2), skipped if this recording was already transcribed
    transcription_result = download_json_from_s3(bucket_name, transcript_s3_key)
    if transcription_result:
        logger.info(f"Step 1: Reusing stored transcript: {transcript_s3_key}")
    else:
        logger.info("Step 1: Running Transcription...")
        transcription_result = transcribe_handler(audio_path)
        # Save raw transcript to S3 (as per ARCHITECTURE line 161)
        upload_json_to_s3(bucket_name, transcript_s3_key, transcription_result)
        logger.info(f"Transcription saved to S3: {transcript_s3_key}")

    # STEP 2: Scoring (L4), returns the cached score if one exists
    logger.info("Step 2: Running AI Scoring...")
    scoring_result = score_handler(meeting_id, transcription_result["transcript"])

    logger.info("--- Pipeline Completed Successfully ---")

    print("\n" + "="*50)
    print(f"FINAL RESULT FOR MEETING: {meeting_id}")
    print("="*50)
    print(f"Transcript: {transcription_result['transcript']}")
    print(f"Score: {scoring_result['score']}/100")
    print(f"Reasoning: {scoring_result['reasoning']}")
    print(f"Source: {scoring_result.get('source', 'unknown')}")
    print("="*50 + "\n")

    return {
        "meeting_id": meeting_id,
        "transcription": transcription_result,
        "scoring": scoring_result
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run AI Call Analyzer Pipeline")
    parser.add_argument("--audio", type=str, required=True, help="Path to the audio file")

    args = parser.parse_args()

    try:
        run_full_pipeline(args.audio)
    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}")
        print(f"\nCRITICAL ERROR: {e.__class__.__name__}: {str(e)}\n")
        sys.exit(1)
