"""Cloud Run service: static UI + short HTTP endpoints.

Audio never passes through this service. The browser streams PCM directly to AssemblyAI with a
one-time token minted here. Only finalized turns come back for /api/suggest.
"""
from __future__ import annotations

import datetime as dt
import threading
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .models import SuggestRequest, Suggestion, TokenResponse
from .settings import Settings
from .suggest import GeminiJsonModel, JsonModel, suggest, warmup

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
        try:
            return suggest(app.state.model, req)
        except ValueError as e:
            raise HTTPException(422, str(e))

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC / "index.html", headers=NO_CACHE)

    app.mount("/static", RevalidatingStatic(directory=STATIC), name="static")
    return app


def factory() -> FastAPI:
    """uvicorn app.main:factory --factory"""
    return create_app()
