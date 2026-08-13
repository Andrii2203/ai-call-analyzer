import os
import boto3
import json
from typing import Any, Dict
from dotenv import load_dotenv
from src.utils.logger import get_logger

load_dotenv()
logger = get_logger(__name__, component="UTILS-S3")

def get_s3_client():
    """Returns a boto3 S3 client configured for LocalStack or real AWS."""
    endpoint_url = os.getenv("LOCALSTACK_ENDPOINT", "http://localhost:4566")
    is_localstack = "localhost" in endpoint_url
    
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url if is_localstack else None,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "test"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "test"),
        region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    )

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
