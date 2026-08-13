import os
import json
from typing import Dict, Any
from groq import Groq
from dotenv import load_dotenv

from src.utils.logger import get_logger
from src.utils.retry import exponential_backoff
from src.utils.dynamodb_utils import get_existing_score, save_score_to_db
from src.utils.s3_utils import upload_json_to_s3
from src.lambdas.models.events import ScoringResponse

# Load environment variables
load_dotenv()

logger = get_logger(__name__, component="L4-SCORE")

SCORING_PROMPT = """
Analyze this sales call and score it 0-100 based on:
- Did the rep ask open questions?
- Did they handle objections?
- Was there a clear next step?

Transcript: {transcript}

IMPORTANT: Return ONLY a valid JSON object with these fields:
{{
  "score": <int 0-100>,
  "reasoning": "<string description of why this score was given>"
}}
"""

@exponential_backoff(
    max_retries=3,
    exceptions=(Exception,),
    initial_delay=2.0
)
def call_groq_api(transcript: str) -> Dict[str, Any]:
    """
    Calls Groq API to score the transcript.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not found in environment.")

    client = Groq(api_key=api_key)
    
    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": SCORING_PROMPT.format(transcript=transcript),
            }
        ],
        model="llama-3.3-70b-versatile",
        response_format={"type": "json_object"},
    )
    
    result_content = chat_completion.choices[0].message.content
    return json.loads(result_content)

def handler(meeting_id: str, transcript: str) -> Dict[str, Any]:
    """
    L4 Lambda Handler: Scores the transcript and saves results.
    """
    logger.info(f"Scoring transcript for meeting_id: {meeting_id}")

    # 1. Idempotency Check
    existing_item = get_existing_score(meeting_id)
    if existing_item:
        logger.info(f"Returning existing score for {meeting_id} from DynamoDB")
        return {
            "meeting_id": meeting_id,
            "score": int(existing_item["score"]),
            "reasoning": existing_item["reasoning"],
            "status": "scored",
            "source": "cache"
        }

    # 2. Call Groq API
    try:
        score_data = call_groq_api(transcript)
        
        # 3. Validate with Pydantic
        response = ScoringResponse(
            meeting_id=meeting_id,
            score=score_data["score"],
            reasoning=score_data["reasoning"],
            status="scored"
        )
        
        # 4. Save to DynamoDB
        save_score_to_db(meeting_id, response.score, response.reasoning)
        
        # 5. Save to S3
        bucket_name = os.getenv("S3_BUCKET_NAME", "sales-score-dev")
        s3_key = f"scores/{meeting_id}/score.json"
        upload_json_to_s3(bucket_name, s3_key, response.model_dump())
        
        logger.info(f"Scoring completed for {meeting_id}. Score: {response.score}")
        
        result = response.model_dump()
        result["source"] = "api"
        return result

    except Exception as e:
        logger.error(f"Failed to score transcript for {meeting_id}: {str(e)}")
        raise
