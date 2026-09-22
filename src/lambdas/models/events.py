from datetime import datetime, timezone

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TranscriptionResponse(BaseModel):
    meeting_id: str
    transcript: str
    word_count: int
    status: str = "transcribed"
    created_at: datetime = Field(default_factory=_utc_now)


class ScoringResponse(BaseModel):
    meeting_id: str
    score: int = Field(ge=0, le=100)
    reasoning: str
    status: str = "scored"
    created_at: datetime = Field(default_factory=_utc_now)
