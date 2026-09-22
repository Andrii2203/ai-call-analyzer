import json
import os
from typing import Any, Dict

import groq
from dotenv import load_dotenv
from groq import Groq
from pydantic import ValidationError

from src.lambdas.models.events import ScoringResponse
from src.utils.dynamodb_utils import get_existing_score, save_score_to_db
from src.utils.logger import get_logger
from src.utils.retry import exponential_backoff
from src.utils.s3_utils import upload_json_to_s3

# Load environment variables
load_dotenv()

logger = get_logger(__name__, component="L4-SCORE")

# llama-3.3-70b-versatile was shut down on Groq on 2026-08-16; Groq recommends gpt-oss-120b.
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"

# Only temporary failures are retried; a bad key or a bad request fails immediately.
RETRYABLE_GROQ_ERRORS = (
    groq.RateLimitError,
    groq.APIConnectionError,
    groq.APITimeoutError,
    groq.InternalServerError,
)

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


class ScoringError(Exception):
    """Scoring failed and retrying will not help."""


@exponential_backoff(
    max_retries=3,
    exceptions=RETRYABLE_GROQ_ERRORS,
    initial_delay=2.0
)
def call_groq_api(transcript: str) -> Dict[str, Any]:
    """
    Calls Groq API to score the transcript.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ScoringError("GROQ_API_KEY not found in environment.")

    client = Groq(api_key=api_key)

    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": SCORING_PROMPT.format(transcript=transcript),
            }
        ],
        model=os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL),
        response_format={"type": "json_object"},
    )

    result_content = chat_completion.choices[0].message.content
    try:
        return json.loads(result_content)
    except (TypeError, json.JSONDecodeError) as e:
        raise ScoringError(f"Model returned invalid JSON: {result_content!r}") from e


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
        try:
            response = ScoringResponse(
                meeting_id=meeting_id,
                score=score_data.get("score"),
                reasoning=score_data.get("reasoning"),
                status="scored"
            )
        except (AttributeError, ValidationError) as e:
            raise ScoringError(f"Model response does not match the schema: {score_data!r}") from e

        # 4. Save to DynamoDB
        save_score_to_db(meeting_id, response.score, response.reasoning)

        # 5. Save to S3
        bucket_name = os.getenv("S3_BUCKET_NAME", "sales-score-dev")
        s3_key = f"scores/{meeting_id}/score.json"
        upload_json_to_s3(bucket_name, s3_key, response.model_dump(mode="json"))

        logger.info(f"Scoring completed for {meeting_id}. Score: {response.score}")

        result = response.model_dump(mode="json")
        result["source"] = "api"
        return result

    except Exception as e:
        logger.error(f"Failed to score transcript for {meeting_id}: {str(e)}")
        raise
