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


Authority = Annotated[str, StringConstraints(pattern=r"^(mine|needs_approval|unclear|nothing_asked)$")]


class Suggestion(BaseModel):
    """Model output contract. Every claim must cite utterance ids that exist in the request.

    Field order is load-bearing: the model fills these in the order they are declared, so naming what
    is being asked and whose decision it is comes before the sentence that answers it. Written the
    other way round, the sentence arrives first and the classification is back-filled to match.
    """

    summary_ja: str = Field(max_length=300)
    asked_for: str = Field(
        max_length=200,
        description="In English, the one thing the other side is asking the engineer to agree to. "
                    "Empty when they have not asked for agreement at all.")
    authority: Authority = Field(
        description="Judge asked_for against the memo. 'mine' when the memo places it inside the "
                    "engineer's own discretion. 'needs_approval' when the memo places it outside — "
                    "including anything the memo does not mention. 'nothing_asked' when no agreement "
                    "is being sought yet. 'unclear' when they are asking for something real but what "
                    "was said does not say which side of the memo it falls on — a deployment with no "
                    "environment named, a sign-off with no owner named, work whose extent was never "
                    "stated. Judge only what was actually said: never supply the missing detail in order "
                    "to reach mine or needs_approval. 'unclear' is the answer whenever you would have "
                    "had to guess it.")
    unconfirmed: list[Unconfirmed] = Field(
        default_factory=list, max_length=5,
        description="What an utterance raised and left open — including a detail of it they never "
                    "gave, when that detail is needed before the engineer can answer. Empty when the "
                    "utterances leave nothing open. Most useful item first.")
    next_line_en: str = Field(
        max_length=300,
        description="Follows from authority and unconfirmed, in that order. needs_approval: say that "
                    "this particular decision needs internal confirmation, naming it — never agree, "
                    "and never substitute an unrelated question for the boundary. unclear: ask for the "
                    "one missing detail that would settle whose decision this is, naming it concretely "
                    "— do not agree and do not defer, because there is not yet anything to defer. "
                    "mine with something "
                    "unconfirmed: ask about unconfirmed[0], naming it. mine with nothing unconfirmed: "
                    "agree, scoped to exactly what was asked. nothing_asked: acknowledge in one "
                    "sentence and ask nothing. Plain English addressed to the other side: never "
                    "write an utterance id such as u1 or m0 in the sentence itself.")
    next_line_ja: str = Field(max_length=300)
    evidence_ids: list[EvidenceId] = Field(min_length=1, max_length=5)
    commits_to_something: bool = Field(
        description="True only if next_line_en actually gives away something the memo does not allow: "
                    "a date, an effort figure, or an approval. Saying that the engineer will confirm "
                    "internally and come back is NOT a commitment, however firmly it is worded — the "
                    "only thing promised there is a follow-up."
    )


SUGGESTION_JSON_SCHEMA: dict = Suggestion.model_json_schema()


class Event(BaseModel):
    """What the engineer did with a card.

    Whether a deferral sentence is one a person will actually say is the only thing about this product
    that cannot be measured offline, and the adopt/hold click is the whole signal. Every field here is
    a category, a count or a duration on purpose: there is no field this model will carry text in, so
    the endpoint cannot become a place where conversation content ends up in the logs.
    """

    session: str = Field(pattern=r"^[0-9a-f]{8,32}$",
                         description="Random per page load, generated client-side. Not a user id: it "
                                     "joins the cards of one sitting and identifies nobody.")
    kind: Annotated[str, StringConstraints(pattern=r"^(shown|adopted|held|copied)$")]
    authority: Authority
    turn: int = Field(ge=1, le=999)
    unconfirmed_count: int = Field(ge=0, le=5)
    commits: bool
    latency_ms: int = Field(ge=0, le=60000)

    model_config = {"extra": "forbid"}


class TokenResponse(BaseModel):
    token: str
    expires_in_seconds: int
    max_session_duration_seconds: int
    sessions_left_today: int
