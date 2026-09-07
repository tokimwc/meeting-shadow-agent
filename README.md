# Meeting Shadow Agent

A silent assistant for Japanese engineers in English technical meetings. It listens to the *other* participants,
flags conditions that are still unconfirmed (environment, deadline, scope, authority, effort), and proposes the
one clarifying line to say next, in English with a Japanese translation. It never speaks, never posts, never commits
on your behalf.

Built for the AssemblyAI Voice Agent Hackathon (lablab.ai, Sep 2026).

## How it works

```
Chrome (Meet tab audio | sample audio)
  -> AudioWorklet: mono PCM16 @ 16 kHz
  -> wss://streaming.assemblyai.com/v3/ws  (Universal-3.5 Pro Realtime, one-time token)
  -> finalized Turn (end_of_turn + formatted)
  -> POST /api/suggest on Cloud Run  (recent turns + your premise memo)
  -> Gemini (JSON schema output)
  -> suggestion card with utterance ids as evidence
```

- Audio goes from the browser straight to AssemblyAI. The Cloud Run service only mints short-lived tokens
  (`expires_in_seconds=60`, `max_session_duration_seconds=90`) and runs short HTTP calls to Gemini.
- Every claim in a suggestion cites utterance ids. A response that cites an id that does not exist is rejected, not repaired.
- A suggestion that would commit to a date, effort, or authority not present in your premise is flagged red.
- Conversation text is not stored. Only counts, latency, and error classes are logged.

## Local development

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest        # network is disabled in tests
```

Run with real providers (keys are injected at process start; nothing is read from files):

```powershell
op run --env-file .env.op -- .\.venv\Scripts\uvicorn.exe app.main:factory --factory --port 8080
```

Open http://127.0.0.1:8080/ and either pick a Meet tab (tick "Share tab audio") or play the sample conversation.

## Status

Week 1 scaffold. Not yet verified against live AssemblyAI or Gemini. See `docs/week1-plan.md` for the go/no-go gates.
