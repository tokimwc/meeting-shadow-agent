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

The September 8 handoff reports G2/G3 passed on the previous deployed version; G1 (remote Meet audio) remains unverified.
Local quality improvements are in `codex/handoff-quality`, not deployed. See [local handoff](docs/2026-09-08-codex-handoff.md)
for changes, checks and remaining live evaluation. Historical measurements do not validate this new prompt/client.

The client batches nearby final turns for 450 ms while preserving their evidence ids, skips simple acknowledgements,
and processes the latest pending context after a model request completes. The displayed latency includes this wait.

Offline regression checks from the worktree:

```powershell
D:/dev/meeting-shadow-agent/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
node --test tests/client.test.cjs
```

The audio evaluator requires 20 distinct WAV cases by default and writes only metrics (no transcript or suggested text).
For the existing three synthetic samples, explicitly choose a three-case smoke run:

```powershell
op run --env-file .env.op -- D:/dev/meeting-shadow-agent/.venv/Scripts/python.exe -m scripts.e2e_eval samples/sample-01.wav samples/sample-02.wav samples/sample-03.wav --min-cases 3 --out docs/eval/e2e-quality-smoke.csv
```

Run from the worktree so its updated prompt is imported. This command needs provider credentials and incurs usage.
A measurement PASS only checks id validity, model-reported commitments and latency; semantic accuracy remains `unreviewed`.
