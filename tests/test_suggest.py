import json

import pytest

from app.models import SuggestRequest
from app.suggest import build_user_prompt, suggest


class FakeModel:
    def __init__(self, payload: dict):
        self.payload = payload
        self.calls = []

    def generate_json(self, *, system, user, schema):
        self.calls.append((system, user, schema))
        return json.dumps(self.payload)


REQ = SuggestRequest(
    premise="Implementation owner. Production commitments need internal approval.",
    utterances=[
        {"id": "u1", "text": "Can you commit to shipping the fix by Friday?", "t_ms": 1200},
    ],
)

GOOD = {
    "summary_ja": "相手は金曜までの対応確約を求めている。",
    "unconfirmed": [{"item": "検証環境か本番環境か", "evidence_ids": ["u1"]}],
    "next_line_en": "Is this for the staging environment or production?",
    "next_line_ja": "検証環境ですか、本番環境ですか？",
    "evidence_ids": ["u1"],
    "commits_to_something": False,
}


def test_prompt_contains_premise_and_ids():
    p = build_user_prompt(REQ)
    assert "Production commitments" in p and "[u1]" in p


def test_valid_suggestion_passes():
    s = suggest(FakeModel(GOOD), REQ)
    assert s.next_line_en.endswith("?") and s.evidence_ids == ["u1"]


def test_unknown_evidence_id_is_refused():
    bad = dict(GOOD, evidence_ids=["u9"])
    with pytest.raises(ValueError, match="u9"):
        suggest(FakeModel(bad), REQ)


def test_unknown_id_inside_unconfirmed_is_refused():
    bad = dict(GOOD, unconfirmed=[{"item": "x", "evidence_ids": ["u2"]}])
    with pytest.raises(ValueError, match="u2"):
        suggest(FakeModel(bad), REQ)
