# Meeting Shadow Agent

A silent assistant for a non-native English speaker in an English technical meeting. It listens to the
*other* participants and, at the end of each of their turns, proposes one English sentence for you to
say — with a Japanese translation and the utterance ids it drew on.

It never speaks, never joins the call, and never sends anything on your behalf. You read the card and
decide.

Built for the AssemblyAI Voice Agent Hackathon (lablab.ai, September 2026).

## What shapes the suggestion

Before the meeting you write a short memo saying what you may settle alone and what you may not:

> 自分は実装担当。staging 検証の合意は自分の裁量で可能。本番反映・納期・スコープ変更・追加工数の約束には社内確認が必要。
>
> *(Implementation owner. Staging validation is mine to agree. Production, dates, scope changes and extra effort need internal approval.)*

A request that falls inside that line gets a sentence that commits. A request outside it gets a
sentence that defers, naming the specific thing that needs approval rather than a generic "let me get
back to you".

## How it works

```
Chrome (Meet tab audio | sample audio)
  -> AudioWorklet: mono PCM16 @ 16 kHz
  -> wss://streaming.assemblyai.com/v3/ws   Universal-3.5 Pro Realtime, one-time token
  -> finalized Turn (end_of_turn + formatted)
  -> POST /api/suggest on Cloud Run         recent turns + your memo
  -> Gemini 2.5 Flash-Lite                  JSON schema output
  -> suggestion card, citing the utterances behind it
```

Two guards, both refusals rather than repairs:

- **Every claim cites utterance ids.** A response citing an id nobody spoke is rejected, not patched
  up — see `suggest()` in [app/suggest.py](app/suggest.py).
- **An open item whose only evidence is your memo is dropped.** The memo says what needs approval; it
  is not evidence that anyone asked for it. If dropping leaves nothing, the whole suggestion is
  refused, because a card reading "nothing open" beside a question about what was just removed is
  worse than no card.

A suggestion that would commit to a date, effort or authority not present in your memo is flagged in
the UI.

Audio goes from the browser straight to AssemblyAI. Cloud Run only mints short-lived tokens
(`expires_in_seconds=60`, `max_session_duration_seconds=90`) and makes short HTTP calls to Gemini; it
never holds the stream. Conversation text is not stored — only counts, latency and error class names
are logged.

This is **not** zero retention. AssemblyAI offers a configurable TTL, and billing and log metadata
outlive it.

## What was measured

Twenty scripted scenarios in [samples/cases.json](samples/cases.json): five conditions (environment,
deadline, scope, authority, effort) crossed with four situations — a condition left undefined, one the
speaker revises mid-conversation, a request that conflicts with the memo, and a conversation where
everything is already settled. Twelve are synthetic audio, eight are read by a person.

Median 1.90 s from the end of speech to the **suggestion being generated**, p90 2.39 s — measured
in-process by the evaluator, without the HTTP round trip or rendering. The browser reports a separate
figure, turn arrival → card, which was 1,234–1,357 ms in the recorded demo. Nothing measures end of
speech → card on screen.

Across four runs the model reported zero dangerous commitments and cited no ids that did not exist.
Both of those are weaker than they sound: the commitment flag is the model's own field about its own
output, and the id check proves a citation exists, not that it supports the claim.

[docs/eval/20cases.md](docs/eval/20cases.md) has all four runs, **including the two prompt changes
that made the suggestions worse and were reverted**, and what the numbers do not support: this is a
developer-authored test suite rather than a field study, and zero failures in twenty trials still
leaves a one-sided 95% upper bound near 14%.

## Local development

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest        # the network is disabled in tests
node --test tests/client.test.cjs
```

Run against real providers (keys are injected at process start; nothing is read from a file on disk):

```powershell
op run --env-file .env.op -- .\.venv\Scripts\uvicorn.exe app.main:factory --factory --port 8080
```

Open http://127.0.0.1:8080/ and either pick a Meet tab (tick "Share tab audio") or play the sample
conversation.

### Rebuilding the evaluation

```powershell
python scripts/make_cases.py                # render the synthetic cases
python scripts/record_cases.py              # record the human ones
op run --env-file .env.op -- python -m scripts.e2e_eval (ls samples/cases/*.wav) --out docs/eval/run.csv
```

The evaluator requires twenty distinct WAV cases by default and writes only measurements — no
transcript, no model text. Pass `--review` to dump the suggestions separately for a human pass; that
file is gitignored on purpose. These commands need provider credentials and cost money.

A measurement PASS checks id validity, self-reported commitments and latency. Whether a suggestion is
*right* is judged by hand against each case's expectations, and that pass is what
[docs/eval/20cases.md](docs/eval/20cases.md) records.

Deploying: [docs/deploy.md](docs/deploy.md), which also lists the traps already paid for.

## Known limitations

- **Non-native speech degrades the transcript on exactly the words a decision turns on.** One human
  take reached the model as "Oh. End of day. Cause visit." An early take turned `Legal` into `Diego`.
- **Situation A and situation D pull against each other.** The suggestion must always find the missing
  condition, and must also recognise when nothing is missing; both are steered from one paragraph, and
  in three of the five settled cases the card asks a question anyway.
- **The daily session cap is a per-process counter** on token minting only; `/api/suggest` is not
  behind it. Fine for a demo behind sign-in, not for anonymous exposure.
- **Whether the memo changes the suggestion is not measured.** All twenty cases share one memo, so
  nothing separates its effect from the prompt simply being cautious. This is the next thing to test.
- Only Chrome-family browsers: the capture path is `getDisplayMedia` with tab audio.

## Licence

MIT — see [LICENSE](LICENSE).
