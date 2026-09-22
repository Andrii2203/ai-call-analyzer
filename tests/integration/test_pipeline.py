import json
import os
import uuid
from unittest.mock import patch

import pytest

from demo.run_pipeline import run_full_pipeline
from src.utils.dynamodb_utils import get_dynamodb_resource
from src.utils.s3_utils import get_s3_client

BUCKET = os.getenv("S3_BUCKET_NAME", "sales-score-dev")
TABLE = os.getenv("DYNAMODB_TABLE_NAME", "SalesScores")


@pytest.fixture
def localstack_setup():
    """Ensure S3 bucket and DynamoDB table exist in LocalStack."""
    s3 = get_s3_client()
    try:
        s3.list_buckets()
    except Exception as e:
        # In CI LocalStack must be there: a skipped test would look like a passed one.
        if os.getenv("REQUIRE_LOCALSTACK") == "1":
            pytest.fail(f"LocalStack is required but not reachable: {e}")
        pytest.skip("LocalStack not available")

    try:
        s3.create_bucket(Bucket=BUCKET)
    except s3.exceptions.BucketAlreadyOwnedByYou:
        pass

    dynamo = get_dynamodb_resource()
    existing_tables = [t.name for t in dynamo.tables.all()]
    if TABLE not in existing_tables:
        dynamo.create_table(
            TableName=TABLE,
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"}
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"}
            ],
            BillingMode="PAY_PER_REQUEST"
        ).wait_until_exists()


@pytest.fixture
def audio_file(tmp_path):
    # Unique content -> unique meeting_id, so earlier runs never pre-fill the cache.
    # The paid APIs are mocked, so the bytes do not need to be real audio.
    path = tmp_path / "call.mp3"
    path.write_bytes(uuid.uuid4().bytes)
    return str(path)


@patch("src.lambdas.transcribe.handler.transcribe_audio")
@patch("src.lambdas.score.handler.call_groq_api")
def test_full_pipeline_integration(mock_groq, mock_transcribe, localstack_setup, audio_file):
    """
    Runs L2 -> L4 with real LocalStack persistence, then runs again on the same file
    and checks that neither paid API is called the second time.
    """
    # 1. Mock External APIs
    mock_transcribe.return_value = "This is a test sales call transcript."
    mock_groq.return_value = {"score": 90, "reasoning": "Excellent handling of objections."}

    # 2. First run: transcribe + score
    first = run_full_pipeline(audio_file)
    meeting_id = first["meeting_id"]
    assert first["scoring"]["source"] == "api"
    mock_transcribe.assert_called_once()
    mock_groq.assert_called_once()

    # 3. Verify LocalStack Persistence
    s3 = get_s3_client()
    transcript_obj = s3.get_object(
        Bucket=BUCKET, Key=f"transcripts/raw/{meeting_id}/transcript.json"
    )
    saved_transcript = json.loads(transcript_obj["Body"].read().decode("utf-8"))
    assert saved_transcript["transcript"] == "This is a test sales call transcript."

    score_obj = s3.get_object(Bucket=BUCKET, Key=f"scores/{meeting_id}/score.json")
    saved_score = json.loads(score_obj["Body"].read().decode("utf-8"))
    assert saved_score["score"] == 90
    assert saved_score["meeting_id"] == meeting_id

    table = get_dynamodb_resource().Table(TABLE)
    db_response = table.get_item(Key={"PK": f"MEETING#{meeting_id}", "SK": "SCORE#v1"})
    assert db_response["Item"]["score"] == 90

    # 4. Second run on the same recording: everything comes from storage
    mock_transcribe.reset_mock()
    mock_groq.reset_mock()
    second = run_full_pipeline(audio_file)

    assert second["meeting_id"] == meeting_id
    assert second["scoring"]["source"] == "cache"
    assert second["scoring"]["score"] == 90
    mock_transcribe.assert_not_called()
    mock_groq.assert_not_called()
