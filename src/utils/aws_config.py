import os
from typing import Any, Dict


def boto3_kwargs() -> Dict[str, Any]:
    """
    Shared boto3 settings. LOCALSTACK_ENDPOINT set (any host, e.g. localhost or a CI
    service name) -> talk to LocalStack; set to an empty string -> real AWS.
    """
    endpoint_url = os.getenv("LOCALSTACK_ENDPOINT", "http://localhost:4566")

    return {
        "endpoint_url": endpoint_url or None,
        "aws_access_key_id": os.getenv("AWS_ACCESS_KEY_ID", "test"),
        "aws_secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY", "test"),
        "region_name": os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
    }
