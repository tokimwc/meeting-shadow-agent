"""Cloud Run service: static UI + short HTTP endpoints.

Audio never passes through this service. The browser streams PCM directly to AssemblyAI with a
one-time token minted here. Only finalized turns come back for /api/suggest.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import threading
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .models import Event, SuggestRequest, Suggestion, TokenResponse
from .settings import Settings
from .suggest import GeminiJsonModel, JsonModel, Refusal, suggest, warmup

STATIC = Path(__file__).parent / "static"
AAI_TOKEN_URL = "https://streaming.assemblyai.com/v3/token"


class DailyCounter:
    # ponytail: in-memory counter. Cloud Run max-instances=1 keeps it coherent for a demo;
    # move to Firestore if instances > 1 or a restart-proof cap is required.
    def __init__(self, cap: int) -> None:
        self.cap = cap
        self._day: dt.date | None = None
        self._n = 0
        self._lock = threading.Lock()

    def take(self) -> int:
        today = dt.date.today()
        with self._lock:
            if self._day != today:
                self._day, self._n = today, 0
            if self._n >= self.cap:
                return -1
            self._n += 1
            return self.cap - self._n


NO_CACHE = {"cache-control": "no-cache"}


def emit(event: str, **fields) -> None:
    """One JSON line on stdout, which is the whole analytics store.

    Cloud Run already forwards stdout to Cloud Logging and parses a JSON line into `jsonPayload`, so
    this is queryable and append-only without a database, a client library or an IAM grant. A store
    the app can read back would be a different decision; nothing here needs one. Only categories,
    counts and durations are ever passed in — see `Event`.
    """
    print(json.dumps({"severity": "INFO", "msa_event": event, **fields}), file=sys.stdout, flush=True)


class RevalidatingStatic(StaticFiles):
    """Serve static files with `no-cache` so a deploy actually reaches browsers.

    StaticFiles sets ETag and Last-Modified but no Cache-Control, which lets a browser treat the file as
    fresh and skip revalidation entirely. A judge who opened the demo once would keep running the old
    client after a redeploy. `no-cache` still allows 304s, so this costs a conditional request, not bytes.
    """

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        response.headers.setdefault("cache-control", "no-cache")
        return response


def create_app(
    settings: Settings | None = None, model: JsonModel | None = None, http: httpx.Client | None = None
) -> FastAPI:
    st = settings or Settings.from_env()
    counter = DailyCounter(st.daily_session_cap)
    app = FastAPI(title="Meeting Shadow Agent", version="0.1.0")
    app.state.model = model
    app.state.http = http or httpx.Client(timeout=10)

    @app.get("/health")
    def health() -> dict:
        return {"ok": True, "mode": st.public_mode}

    @app.post("/api/token", response_model=TokenResponse)
    def token() -> TokenResponse:
        if not st.assemblyai_api_key:
            raise HTTPException(503, "ASSEMBLYAI_API_KEY not configured")
        left = counter.take()
        if left < 0:
            raise HTTPException(429, "daily demo cap reached; try again tomorrow")
        r = app.state.http.get(
            AAI_TOKEN_URL,
            headers={"Authorization": st.assemblyai_api_key},
            params={
                "expires_in_seconds": st.token_expires_seconds,
                "max_session_duration_seconds": st.max_session_seconds,
            },
        )
        if r.status_code != 200:
            raise HTTPException(502, f"token provider error {r.status_code}")
        # A session is starting: warm the model in the background so the first suggestion is not a cold call.
        if app.state.model is None and st.google_cloud_project:
            app.state.model = GeminiJsonModel(project=st.google_cloud_project, location=st.gemini_location, model=st.gemini_model)
        if app.state.model is not None:
            threading.Thread(target=warmup, args=(app.state.model,), daemon=True).start()
        return TokenResponse(
            token=r.json()["token"],
            expires_in_seconds=st.token_expires_seconds,
            max_session_duration_seconds=st.max_session_seconds,
            sessions_left_today=left,
        )

    @app.post("/api/suggest", response_model=Suggestion)
    def api_suggest(req: SuggestRequest) -> Suggestion:
        if app.state.model is None:
            if not st.google_cloud_project:
                raise HTTPException(503, "GOOGLE_CLOUD_PROJECT not configured")
            app.state.model = GeminiJsonModel(
                project=st.google_cloud_project, location=st.gemini_location, model=st.gemini_model
            )
        t0 = dt.datetime.now()
        try:
            s = suggest(app.state.model, req)
        except ValueError as e:
            # The refusal rate measured offline was close to one call in five; this is the same number
            # in real use, for free. Only a Refusal carries a message of ours - anything else, a
            # ValidationError included, is recorded and returned by class name alone.
            reason = str(e)[:120] if isinstance(e, Refusal) else type(e).__name__
            emit("refused", reason=reason, turns=len(req.utterances))
            raise HTTPException(422, reason)
        emit("suggested", authority=s.authority, unconfirmed_count=len(s.unconfirmed),
             commits=s.commits_to_something, turns=len(req.utterances),
             ms=int((dt.datetime.now() - t0).total_seconds() * 1000))
        return s

    @app.post("/api/event", status_code=204)
    def api_event(ev: Event) -> None:
        """What the engineer did with a card. Categories only; the model forbids anything else."""
        emit("card", **ev.model_dump())

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC / "index.html", headers=NO_CACHE)

    app.mount("/static", RevalidatingStatic(directory=STATIC), name="static")
    return app


def factory() -> FastAPI:
    """uvicorn app.main:factory --factory"""
    return create_app()
