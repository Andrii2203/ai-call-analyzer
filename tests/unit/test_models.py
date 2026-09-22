import json

import pytest
from pydantic import ValidationError

from src.lambdas.models.events import ScoringResponse, TranscriptionResponse


@pytest.mark.parametrize("score", [0, 50, 100])
def test_score_within_bounds_is_accepted(score):
    assert ScoringResponse(meeting_id="m1", score=score, reasoning="r").score == score


@pytest.mark.parametrize("score", [-1, 101])
def test_score_outside_bounds_is_rejected(score):
    with pytest.raises(ValidationError):
        ScoringResponse(meeting_id="m1", score=score, reasoning="r")


def test_json_dump_is_serializable_with_utc_timestamp():
    data = TranscriptionResponse(meeting_id="m1", transcript="hi", word_count=1).model_dump(
        mode="json"
    )
    json.dumps(data)
    assert data["created_at"].endswith("Z") or data["created_at"].endswith("+00:00")
