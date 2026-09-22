import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import boto3
from dotenv import load_dotenv

from src.utils.aws_config import boto3_kwargs
from src.utils.logger import get_logger

load_dotenv()
logger = get_logger(__name__, component="UTILS-DYNAMO")

def get_dynamodb_resource():
    """Returns a boto3 DynamoDB resource configured for LocalStack or real AWS."""
    return boto3.resource("dynamodb", **boto3_kwargs())

def get_existing_score(meeting_id: str) -> Optional[Dict[str, Any]]:
    """
    Checks DynamoDB for an existing score for the given meeting_id (Idempotency check).
    """
    table_name = os.getenv("DYNAMODB_TABLE_NAME", "SalesScores")
    dynamo = get_dynamodb_resource()
    table = dynamo.Table(table_name)
    
    try:
        response = table.get_item(
            Key={
                "PK": f"MEETING#{meeting_id}",
                "SK": "SCORE#v1"
            }
        )
        item = response.get("Item")
        if item:
            logger.info(f"Found existing score in DynamoDB for meeting_id: {meeting_id}")
            return item
        return None
    except Exception as e:
        logger.error(f"Error checking DynamoDB for existing score: {str(e)}")
        # We don't want to break the flow if DynamoDB is just down,
        # but for strict idempotency we should
        return None

def save_score_to_db(meeting_id: str, score: int, reasoning: str):
    """
    Saves the score and reasoning to DynamoDB.
    """
    table_name = os.getenv("DYNAMODB_TABLE_NAME", "SalesScores")
    dynamo = get_dynamodb_resource()
    table = dynamo.Table(table_name)
    
    item = {
        "PK": f"MEETING#{meeting_id}",
        "SK": "SCORE#v1",
        "score": score,
        "reasoning": reasoning,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    try:
        table.put_item(Item=item)
        logger.info(f"Successfully saved score to DynamoDB for meeting_id: {meeting_id}")
    except Exception as e:
        logger.error(f"Failed to save to DynamoDB: {str(e)}")
        raise
