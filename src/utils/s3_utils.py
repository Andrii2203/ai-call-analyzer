import json
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

from src.utils.aws_config import boto3_kwargs
from src.utils.logger import get_logger

load_dotenv()
logger = get_logger(__name__, component="UTILS-S3")

def get_s3_client():
    """Returns a boto3 S3 client configured for LocalStack or real AWS."""
    return boto3.client("s3", **boto3_kwargs())

def upload_json_to_s3(bucket: str, key: str, data: Dict[str, Any]):
    """Uploads a dictionary as a JSON file to S3."""
    s3 = get_s3_client()
    try:
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=json.dumps(data, ensure_ascii=False),
            ContentType="application/json"
        )
        logger.info(f"Successfully uploaded JSON to s3://{bucket}/{key}")
    except Exception as e:
        logger.error(f"Failed to upload to S3: {str(e)}")
        raise

def download_json_from_s3(bucket: str, key: str) -> Optional[Dict[str, Any]]:
    """Returns the JSON object stored at s3://bucket/key, or None if it does not exist."""
    s3 = get_s3_client()
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
            return None
        logger.error(f"Failed to read s3://{bucket}/{key}: {str(e)}")
        raise
    return json.loads(response["Body"].read().decode("utf-8"))
