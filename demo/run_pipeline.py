import os
import argparse
import json
from dotenv import load_dotenv

from src.lambdas.transcribe.handler import handler as transcribe_handler
from src.lambdas.score.handler import handler as score_handler
from src.utils.logger import get_logger
from src.utils.s3_utils import upload_json_to_s3

# Load environment variables
load_dotenv()

logger = get_logger(__name__, component="DEMO-PIPELINE")

def run_full_pipeline(audio_path: str):
    """
    Orchestrates the full pipeline: Transcription -> Scoring -> Storage.
    """
    logger.info(f"--- Starting Pipeline for {audio_path} ---")

    if not os.path.exists(audio_path):
        logger.error(f"Audio file not found: {audio_path}")
        return

    try:
        # STEP 1: Transcription (L2)
        logger.info("Step 1: Running Transcription...")
        transcription_result = transcribe_handler(audio_path)
        meeting_id = transcription_result["meeting_id"]
        transcript = transcription_result["transcript"]
        
        # Save raw transcript to S3 (as per ARCHITECTURE line 161)
        bucket_name = os.getenv("S3_BUCKET_NAME", "sales-score-dev")
        transcript_s3_key = f"transcripts/raw/{meeting_id}/transcript.json"
        upload_json_to_s3(bucket_name, transcript_s3_key, transcription_result)
        
        logger.info(f"Transcription saved to S3: {transcript_s3_key}")

        # STEP 2: Scoring (L4)
        logger.info("Step 2: Running AI Scoring...")
        scoring_result = score_handler(meeting_id, transcript)
        
        logger.info("--- Pipeline Completed Successfully ---")
        
        # Final output for demo
        final_output = {
            "meeting_id": meeting_id,
            "transcription": transcription_result,
            "scoring": scoring_result
        }
        
        print("\n" + "="*50)
        print(f"FINAL RESULT FOR MEETING: {meeting_id}")
        print("="*50)
        print(f"Score: {scoring_result['score']}/100")
        print(f"Reasoning: {scoring_result['reasoning']}")
        print(f"Source: {scoring_result.get('source', 'unknown')}")
        print("="*50 + "\n")
        
        return final_output

    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}")
        print(f"\nCRITICAL ERROR: {str(e)}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run AI Call Analyzer Pipeline")
    parser.add_argument("--audio", type=str, required=True, help="Path to the audio file")
    
    args = parser.parse_args()
    
    run_full_pipeline(args.audio)
