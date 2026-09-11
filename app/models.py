from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

# u<N> = an utterance by others; m0 = the engineer's own premise memo (a legitimate source for "unconfirmed" items)
MEMO_ID = "m0"
EvidenceId = Annotated[str, StringConstraints(pattern=r"^(u[0-9]{1,6}|m0)$")]


class Utterance(BaseModel):
    """One finalized AssemblyAI turn (end_of_turn=True). id is assigned client-side."""

    id: str = Field(pattern=r"^u[0-9]{1,6}$")
    text: str = Field(min_length=1, max_length=2000)
    t_ms: int = Field(ge=0)


class SuggestRequest(BaseModel):
    premise: str = Field(default="", max_length=1000, description="Short pre-meeting memo written by the engineer.")
    utterances: list[Utterance] = Field(min_length=1, max_length=40)


class Unconfirmed(BaseModel):
    item: str = Field(max_length=200,
                      description="Something the OTHER side raised and left open. Not a category from the memo.")
    evidence_ids: list[EvidenceId] = Field(
        min_length=1, max_length=5,
        description="Must include the u-id of the utterance that raised this. m0 alone is not enough: "
                    "the memo says what needs approval, it is not evidence that anyone asked for it.")


class Suggestion(BaseModel):
    """Model output contract. Every claim must cite utterance ids that exist in the request."""

    summary_ja: str = Field(max_length=300)
    unconfirmed: list[Unconfirmed] = Field(
        default_factory=list, max_length=5,
        description="Empty when the utterances leave nothing open. Most useful item first.")
    next_line_en: str = Field(
        max_length=300,
        description="Asks about unconfirmed[0], naming it concretely. When unconfirmed is empty, "
                    "acknowledge in one sentence and ask nothing.")
    next_line_ja: str = Field(max_length=300)
    evidence_ids: list[EvidenceId] = Field(min_length=1, max_length=5)
    commits_to_something: bool = Field(
        description="True if next_line_en promises a date, effort, or authority that is not in the premise."
    )


SUGGESTION_JSON_SCHEMA: dict = Suggestion.model_json_schema()


class TokenResponse(BaseModel):
    token: str
    expires_in_seconds: int
    max_session_duration_seconds: int
    sessions_left_today: int
