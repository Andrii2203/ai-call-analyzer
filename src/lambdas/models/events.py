from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class TranscriptionResponse(BaseModel):
    meeting_id: str
    transcript: str
    word_count: int
    status: str = "transcribed"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ScoringResponse(BaseModel):
    meeting_id: str
    score: int = Field(ge=0, le=100)
    reasoning: str
    status: str = "scored"
    created_at: datetime = Field(default_factory=datetime.utcnow)
