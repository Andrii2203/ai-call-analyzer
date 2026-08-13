import pytest
import os
import json
from unittest.mock import patch
from src.lambdas.transcribe.handler import handler as transcribe_handler
from src.lambdas.score.handler import handler as score_handler
from src.utils.s3_utils import get_s3_client
from src.utils.dynamodb_utils import get_dynamodb_resource

@pytest.fixture
def localstack_setup():
    """Ensure S3 bucket and DynamoDB table exist in LocalStack."""
    # This assumes LocalStack is running
    s3 = get_s3_client()
    bucket = "sales-score-dev"
    try:
        s3.create_bucket(Bucket=bucket)
    except s3.exceptions.BucketAlreadyOwnedByYou:
        pass
    except Exception:
        pytest.skip("LocalStack S3 not available")
        
    dynamo = get_dynamodb_resource()
    table_name = "SalesScores"
    try:
        dynamo.create_table(
            TableName=table_name,
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"}
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"}
            ],
            BillingMode="PAY_PER_REQUEST"
        )
    except Exception:
        # Table might already exist
        pass

    return {
        "bucket": bucket,
        "table": table_name
    }

@patch("src.lambdas.transcribe.handler.transcribe_audio")
@patch("src.lambdas.score.handler.call_groq_api")
def test_full_pipeline_integration(mock_groq, mock_transcribe, localstack_setup):
    """
    Tests the interaction between L2 and L4 with LocalStack persistence.
    """
    # 1. Mock External APIs
    mock_transcribe.return_value = "This is a test sales call transcript."
    mock_groq.return_value = {"score": 90, "reasoning": "Excellent handling of objections."}
    
    # 2. Run Transcribe (L2)
    # We use a dummy path since transcribe_audio is mocked
    l2_result = transcribe_handler("dummy.mp3")
    meeting_id = l2_result["meeting_id"]
    
    # 3. Run Score (L4)
    l4_result = score_handler(meeting_id, l2_result["transcript"])
    
    # 4. Verify LocalStack Persistence
    s3 = get_s3_client()
    bucket = localstack_setup["bucket"]
    
    # Check S3 for score
    s3_response = s3.get_object(Bucket=bucket, Key=f"scores/{meeting_id}/score.json")
    saved_score = json.loads(s3_response["Body"].read().decode('utf-8'))
    
    assert saved_score["score"] == 90
    assert saved_score["meeting_id"] == meeting_id
    
    # Check DynamoDB for score
    dynamo = get_dynamodb_resource()
    table = dynamo.Table(localstack_setup["table"])
    db_response = table.get_item(Key={"PK": f"MEETING#{meeting_id}", "SK": "SCORE#v1"})
    
    assert db_response["Item"]["score"] == 90
    
    # 5. Verify Idempotency (L4 should not call Groq again)
    mock_groq.reset_mock()
    score_handler(meeting_id, l2_result["transcript"])
    mock_groq.assert_not_called()
