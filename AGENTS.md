# Agent instructions

## AssemblyAI

Always fetch https://www.assemblyai.com/docs/llms.txt before writing AssemblyAI code.
The API has changed — do not rely on memorized parameter names.

Verified 2026-09-07 for `speech_model=universal-3-5-pro` (realtime):
- primary knob is `mode` (`min_latency` | `balanced` | `max_accuracy`); `format_turns` and `end_of_turn_confidence_threshold` are ignored on this model.
- language pin is `language_codes` (plural). `prompt` max 1750 chars. `keyterms_prompt` max 100 terms.
- audio: `pcm_s16le`, mono, 16 kHz, binary frames of 50–1000 ms, never faster than real time.
- browser auth: server mints `GET https://streaming.assemblyai.com/v3/token?expires_in_seconds=..&max_session_duration_seconds=..`
  (raw key in `Authorization`, no `Bearer`); client passes `?token=` and no header. Tokens are single-use.
- always send `{"type":"Terminate"}`; an abandoned socket bills until the 3 h cap.

Docs MCP (optional, on-demand lookups): `claude mcp add assemblyai-docs --transport http https://mcp.assemblyai.com/docs`

## Hard boundaries

- The API key exists only in the process environment (`op run`) or Cloud Run Secret Manager. Never in files, logs, fixtures, or client code.
- Tests deny network access (`pytest-socket`). Providers stay behind the `JsonModel` protocol and `httpx` injection.
- No character IP, no real person's voice in samples. No transcript persistence.
- Anthropic credit is for evaluation only; the runtime depends on AssemblyAI + Gemini only.
