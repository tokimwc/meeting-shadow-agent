from __future__ import annotations

from pydantic import BaseModel, Field


class Utterance(BaseModel):
    """One finalized AssemblyAI turn (end_of_turn=True). id is assigned client-side."""

    id: str = Field(pattern=r"^u[0-9]{1,6}$")
    text: str = Field(min_length=1, max_length=2000)
    t_ms: int = Field(ge=0)


class SuggestRequest(BaseModel):
    premise: str = Field(default="", max_length=1000, description="Short pre-meeting memo written by the engineer.")
    utterances: list[Utterance] = Field(min_length=1, max_length=40)


class Unconfirmed(BaseModel):
    item: str = Field(max_length=200)
    evidence_ids: list[str] = Field(min_length=1, max_length=5)


class Suggestion(BaseModel):
    """Model output contract. Every claim must cite utterance ids that exist in the request."""

    summary_ja: str = Field(max_length=300)
    unconfirmed: list[Unconfirmed] = Field(default_factory=list, max_length=5)
    next_line_en: str = Field(max_length=300)
    next_line_ja: str = Field(max_length=300)
    evidence_ids: list[str] = Field(min_length=1, max_length=5)
    commits_to_something: bool = Field(
        description="True if next_line_en promises a date, effort, or authority that is not in the premise."
    )


SUGGESTION_JSON_SCHEMA: dict = Suggestion.model_json_schema()


class TokenResponse(BaseModel):
    token: str
    expires_in_seconds: int
    max_session_duration_seconds: int
    sessions_left_today: int
