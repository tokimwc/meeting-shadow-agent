import json

import httpx
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings

ENV = {
    "ASSEMBLYAI_API_KEY": "test-key-not-real",
    "GOOGLE_CLOUD_PROJECT": "demo-msa",
    "MSA_DAILY_SESSION_CAP": "2",
    "MSA_TOKEN_EXPIRES_SECONDS": "60",
    "MSA_MAX_SESSION_SECONDS": "90",
}


class FakeModel:
    def generate_json(self, *, system, user, schema):
        return json.dumps({
            "summary_ja": "要約", "unconfirmed": [], "next_line_en": "Could you clarify the environment?",
            "next_line_ja": "環境を教えてください", "evidence_ids": ["u1"], "commits_to_something": False,
        })


def fake_aai(request: httpx.Request) -> httpx.Response:
    assert request.url.host == "streaming.assemblyai.com"
    assert request.headers["Authorization"] == "test-key-not-real"
    assert request.url.params["expires_in_seconds"] == "60"
    assert request.url.params["max_session_duration_seconds"] == "90"
    return httpx.Response(200, json={"token": "tmp-token", "expires_in_seconds": 60})


def make_client():
    http = httpx.Client(transport=httpx.MockTransport(fake_aai))
    app = create_app(Settings.from_env(ENV), model=FakeModel(), http=http)
    return TestClient(app)


def test_health():
    assert make_client().get("/health").json()["ok"] is True


def test_token_mints_one_time_token_and_counts_down():
    c = make_client()
    r1 = c.post("/api/token").json()
    assert r1["token"] == "tmp-token" and r1["max_session_duration_seconds"] == 90 and r1["sessions_left_today"] == 1
    assert c.post("/api/token").json()["sessions_left_today"] == 0
    assert c.post("/api/token").status_code == 429


def test_suggest_roundtrip():
    r = make_client().post("/api/suggest", json={"premise": "", "utterances": [{"id": "u1", "text": "hi", "t_ms": 0}]})
    assert r.status_code == 200 and r.json()["evidence_ids"] == ["u1"]


def test_suggest_rejects_empty_utterances():
    assert make_client().post("/api/suggest", json={"premise": "", "utterances": []}).status_code == 422


def test_suggest_without_project_is_503_not_500():
    http = httpx.Client(transport=httpx.MockTransport(fake_aai))
    app = create_app(Settings.from_env(dict(ENV, GOOGLE_CLOUD_PROJECT="")), model=None, http=http)
    r = TestClient(app).post("/api/suggest", json={"premise": "", "utterances": [{"id": "u1", "text": "hi", "t_ms": 0}]})
    assert r.status_code == 503


def test_settings_reject_out_of_range_token_ttl():
    import pytest
    with pytest.raises(ValueError):
        Settings.from_env(dict(ENV, MSA_TOKEN_EXPIRES_SECONDS="601"))


def test_static_and_index_revalidate():
    """A redeploy must reach a browser that already opened the demo once."""
    with TestClient(create_app()) as c:
        for path in ("/", "/static/app.js"):
            assert c.get(path).headers["cache-control"] == "no-cache", path
