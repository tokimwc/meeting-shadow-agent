"""Runtime settings. Every secret comes from the environment at process start; nothing is read from files."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    assemblyai_api_key: str
    google_cloud_project: str
    gemini_location: str
    gemini_model: str
    token_expires_seconds: int
    max_session_seconds: int
    daily_session_cap: int
    public_mode: str  # "demo" (sample audio + Meet tab) | "private"

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Settings":
        e = os.environ if env is None else env
        exp = int(e.get("MSA_TOKEN_EXPIRES_SECONDS", "60"))
        mx = int(e.get("MSA_MAX_SESSION_SECONDS", "90"))
        # Ranges are the AssemblyAI /v3/token limits (expires_in_seconds 1..600, max_session_duration_seconds 60..10800).
        if not 1 <= exp <= 600:
            raise ValueError("MSA_TOKEN_EXPIRES_SECONDS must be 1..600")
        if not 60 <= mx <= 10800:
            raise ValueError("MSA_MAX_SESSION_SECONDS must be 60..10800")
        return cls(
            # strip: a secret piped into Secret Manager picked up a trailing CRLF once and httpx refused the header
            assemblyai_api_key=e.get("ASSEMBLYAI_API_KEY", "").strip(),
            google_cloud_project=e.get("GOOGLE_CLOUD_PROJECT", ""),
            gemini_location=e.get("MSA_GEMINI_LOCATION", "global"),
            gemini_model=e.get("MSA_GEMINI_MODEL", "gemini-2.5-flash-lite"),
            token_expires_seconds=exp,
            max_session_seconds=mx,
            daily_session_cap=int(e.get("MSA_DAILY_SESSION_CAP", "200")),
            public_mode=e.get("MSA_PUBLIC_MODE", "demo"),
        )
