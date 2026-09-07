"""Suggestion generation. The model sits behind a Protocol so tests never touch the network."""
from __future__ import annotations

import json
from typing import Any, Protocol

from .models import SUGGESTION_JSON_SCHEMA, SuggestRequest, Suggestion

SYSTEM = (
    "You assist a Japanese engineer who is listening to an English technical meeting. "
    "You only see the OTHER participants' utterances plus the engineer's short premise memo. "
    "Tasks: (1) summarize the latest exchange in Japanese in at most 2 sentences; "
    "(2) list conditions that are still UNCONFIRMED and that the engineer must not promise on "
    "(environment, deadline, scope, authority, effort); "
    "(3) propose exactly one next line for the engineer in English, with a Japanese translation. "
    "The next line must ASK or DEFER. It must never commit to a date, effort, or decision that is not in the premise. "
    "Cite utterance ids for every claim and never invent ids. "
    "If nothing is unconfirmed, say so and propose a neutral acknowledgement. "
    "Output JSON only, matching the provided schema."
)


class JsonModel(Protocol):
    def generate_json(self, *, system: str, user: str, schema: dict[str, Any]) -> str: ...


class GeminiJsonModel:
    """google-genai via Application Default Credentials. Constructed only in production; tests inject a fake."""

    def __init__(self, *, project: str, location: str, model: str) -> None:
        from google import genai
        from google.genai import types

        if not project:
            raise ValueError("GOOGLE_CLOUD_PROJECT is required")
        self._types = types
        self._model = model
        self._client = genai.Client(
            enterprise=True, project=project, location=location, http_options=types.HttpOptions(api_version="v1")
        )

    def generate_json(self, *, system: str, user: str, schema: dict[str, Any]) -> str:
        t = self._types
        r = self._client.models.generate_content(
            model=self._model,
            contents=user,
            config=t.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_json_schema=schema,
                max_output_tokens=600,
                temperature=0.2,
                automatic_function_calling=t.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
        return r.text or ""


def build_user_prompt(req: SuggestRequest) -> str:
    lines = [f"PREMISE (engineer memo): {req.premise or '(none)'}", "UTTERANCES (others, oldest first):"]
    lines += [f"[{u.id}] {u.text}" for u in req.utterances]
    return "\n".join(lines)


def suggest(model: JsonModel, req: SuggestRequest) -> Suggestion:
    raw = model.generate_json(system=SYSTEM, user=build_user_prompt(req), schema=SUGGESTION_JSON_SCHEMA)
    s = Suggestion.model_validate(json.loads(raw))
    known = {u.id for u in req.utterances}
    cited = set(s.evidence_ids) | {i for u in s.unconfirmed for i in u.evidence_ids}
    if not cited <= known:
        # ponytail: refuse rather than repair. A suggestion with fabricated evidence is worse than none.
        raise ValueError(f"model cited unknown utterance ids: {sorted(cited - known)}")
    return s
