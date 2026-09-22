import json
from types import SimpleNamespace
from unittest.mock import patch

import groq
import httpx
import pytest

from src.lambdas.score import handler as score_module
from src.lambdas.score.handler import ScoringError, call_groq_api, handler


def completion(content):
    message = SimpleNamespace(content=content)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def rate_limit_error():
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(429, request=request)
    return groq.RateLimitError("rate limited", response=response, body=None)


@pytest.fixture(autouse=True)
def groq_env(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.delenv("GROQ_MODEL", raising=False)


@pytest.fixture
def sleeps():
    with patch("src.utils.retry.time.sleep") as mock_sleep:
        yield mock_sleep


@pytest.fixture
def storage():
    """Replaces DynamoDB and S3 so the handler logic is tested on its own."""
    with patch.object(score_module, "get_existing_score", return_value=None) as get_existing, \
         patch.object(score_module, "save_score_to_db") as save_db, \
         patch.object(score_module, "upload_json_to_s3") as upload_s3:
        yield SimpleNamespace(get_existing=get_existing, save_db=save_db, upload_s3=upload_s3)


def test_call_groq_api_uses_supported_default_model(sleeps):
    with patch.object(score_module, "Groq") as groq_cls:
        create = groq_cls.return_value.chat.completions.create
        create.return_value = completion('{"score": 80, "reasoning": "ok"}')
        assert call_groq_api("transcript") == {"score": 80, "reasoning": "ok"}
    assert create.call_args.kwargs["model"] == "openai/gpt-oss-120b"
    assert create.call_args.kwargs["response_format"] == {"type": "json_object"}


def test_model_can_be_overridden_by_env(monkeypatch, sleeps):
    monkeypatch.setenv("GROQ_MODEL", "qwen/qwen3.8-27b")
    with patch.object(score_module, "Groq") as groq_cls:
        create = groq_cls.return_value.chat.completions.create
        create.return_value = completion('{"score": 80, "reasoning": "ok"}')
        call_groq_api("transcript")
    assert create.call_args.kwargs["model"] == "qwen/qwen3.8-27b"


def test_missing_api_key_fails_fast(monkeypatch, sleeps):
    monkeypatch.delenv("GROQ_API_KEY")
    with pytest.raises(ScoringError, match="GROQ_API_KEY"):
        call_groq_api("transcript")
    sleeps.assert_not_called()


def test_rate_limit_is_retried_then_succeeds(sleeps):
    with patch.object(score_module, "Groq") as groq_cls:
        create = groq_cls.return_value.chat.completions.create
        create.side_effect = [
            rate_limit_error(),
            rate_limit_error(),
            completion('{"score": 55, "reasoning": "fine"}'),
        ]
        assert call_groq_api("transcript")["score"] == 55
    assert create.call_count == 3
    assert sleeps.call_count == 2


def test_invalid_json_is_not_retried(sleeps):
    with patch.object(score_module, "Groq") as groq_cls:
        groq_cls.return_value.chat.completions.create.return_value = completion("not json")
        with pytest.raises(ScoringError, match="invalid JSON"):
            call_groq_api("transcript")
    sleeps.assert_not_called()


def test_handler_scores_and_saves_json_ready_result(storage):
    model_output = {"score": 90, "reasoning": "Good"}
    with patch.object(score_module, "call_groq_api", return_value=model_output):
        result = handler("m1", "transcript")

    assert result["score"] == 90
    assert result["source"] == "api"
    storage.save_db.assert_called_once_with("m1", 90, "Good")
    bucket, key, body = storage.upload_s3.call_args.args
    assert key == "scores/m1/score.json"
    json.dumps(body)  # must be serializable, S3 stores it as JSON


def test_handler_returns_cached_score_without_calling_groq(storage):
    storage.get_existing.return_value = {"score": 70, "reasoning": "cached"}
    with patch.object(score_module, "call_groq_api") as groq_call:
        result = handler("m1", "transcript")
    groq_call.assert_not_called()
    assert result == {
        "meeting_id": "m1",
        "score": 70,
        "reasoning": "cached",
        "status": "scored",
        "source": "cache",
    }


@pytest.mark.parametrize("model_output", [
    {"score": 150, "reasoning": "too high"},
    {"reasoning": "no score"},
    ["not", "an", "object"],
])
def test_handler_rejects_output_outside_schema(storage, model_output):
    with patch.object(score_module, "call_groq_api", return_value=model_output):
        with pytest.raises(ScoringError, match="schema"):
            handler("m1", "transcript")
    storage.save_db.assert_not_called()
    storage.upload_s3.assert_not_called()
