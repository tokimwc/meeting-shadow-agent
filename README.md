# Meeting Shadow Agent

A silent assistant for a non-native English speaker in an English technical meeting. It listens to the
*other* participants and, at the end of each of their turns, proposes one English sentence for you to
say — with a Japanese translation and the utterance ids it drew on.

It never speaks, never joins the call, and never sends anything on your behalf. You read the card and
decide.

Built for the AssemblyAI Voice Agent Hackathon (lablab.ai, September 2026).

**[docs/replay/](docs/replay/index.html) replays four recorded runs** — the transcripts, the
suggestions and the measured times exactly as the evaluation captured them, including the one that
gets it wrong. No sign-in, no microphone, nothing generated when you press play. The live app is
behind IAP because it mints AssemblyAI tokens.

## What shapes the suggestion

Before the meeting you write a short memo saying what you may settle alone and what you may not:

> 自分は実装担当。staging 検証の合意は自分の裁量で可能。本番反映・納期・スコープ変更・追加工数の約束には社内確認が必要。
>
> *(Implementation owner. Staging validation is mine to agree. Production, dates, scope changes and extra effort need internal approval.)*

The card names the decision before it offers a sentence: what the other side is asking you to agree
to, and whether it is yours to agree. A request inside the line gets a sentence that commits. One
outside it gets a sentence that defers, naming the specific thing that needs approval rather than a
generic "let me get back to you". A request whose side of the line nobody named — "deploy the fix by
Friday", with no environment — gets neither: it asks which was meant, because agreeing would require
guessing.

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

- **Whose decision it is, and a sentence that gives it away, cannot both stand.** If the suggestion
  classifies a request as needing approval and also reports that it committed to something, the
  suggestion is refused rather than shown.

A suggestion that would commit to a date, effort or authority not present in your memo is flagged in
the UI. That flag is the model's own report about its own sentence; see the limits below.

Audio goes from the browser straight to AssemblyAI. Cloud Run only mints short-lived tokens
(`expires_in_seconds=60`, `max_session_duration_seconds=90`) and makes short HTTP calls to Gemini; it
never holds the stream.

This is **not** zero retention. AssemblyAI offers a configurable TTL, and billing and log metadata
outlive it.

### What is recorded, exactly

There is no database. Nothing here is read back by the app; it is written once, as a JSON line on
stdout, which Cloud Run forwards to Cloud Logging.

Per suggestion, the server writes: the authority classification, how many open items there were,
the self-reported commitment flag, how many turns were in the request, and the milliseconds it took.
On a refusal it writes the reason — and only when that reason is one of ours. Pydantic's
`ValidationError` is also a `ValueError`, and its message quotes the input that failed, which here is
the model's own sentences; those are recorded by class name alone, and
[`Refusal`](app/suggest.py) exists to make that a type distinction rather than a comment.

When a card appears, and when you adopt, hold or copy it, the browser posts the same categories plus
a random id generated per page load. That id joins the cards of one sitting and identifies nobody.
The [`Event`](app/models.py) model has no field that will carry text and forbids extra keys, so the
endpoint cannot become the place transcripts end up.

**Not recorded anywhere:** the utterances, the suggestion, the memo, your identity. This is the one
question about the product that offline evaluation cannot answer — whether a person under
conversational pressure actually says the deferral sentence — and the adopt/hold click is the whole
signal. Keeping the click while discarding the words is the only version of that worth shipping to
someone whose meetings are confidential.

Adoption rate by classification, which is the number that matters:

```
gcloud logging read 'jsonPayload.msa_event="card"' --format=json --project meeting-shadow-toki-260907   | jq -r '[.[].jsonPayload | {authority, kind}] | group_by(.authority)[]
      | {authority: .[0].authority, shown: map(select(.kind=="shown")) | length,
         adopted: map(select(.kind=="adopted")) | length}'
```

## What was measured

Twenty scripted scenarios in [samples/cases.json](samples/cases.json): five conditions (environment,
deadline, scope, authority, effort) crossed with four situations — a condition left undefined, one the
speaker revises mid-conversation, a request that conflicts with the memo, and a conversation where
everything is already settled. Twelve are synthetic audio, eight are read by a person.

On the shipped contract, 58 of 62 turns returned a suggestion; over those, median 2.02 s from the end
of speech to the **suggestion being generated**, p90 2.55 s — measured in-process by the evaluator, without the HTTP round trip or rendering. The browser reports a separate
figure, turn arrival → card, which was 1,234–1,357 ms in the recorded demo. Nothing measures end of
speech → card on screen.

The claim that survives repetition is narrow, and it is the one the product rests on. Repeating one
configuration over the cases where the memo decides the answer
([docs/eval/stability.md](docs/eval/stability.md)): when the memo **grants** what is being asked, the
the shipped contract agreed on all 15 calls. When the memo **withholds** it, 13 of 15 calls deferred;
one answered `unclear` and one returned no card because the provider call failed. Where the request never named which side of the memo it fell on,
the answer is safe 11 times in 12 but is usually a deferral rather than the question that would
settle it.

Three things the numbers do not support:

- **This is a developer-authored test suite, not a field study.** The cases were written by the
  person building the agent, and the shipped prompt was chosen after seeing where it failed on them.
  Even the audio run gets final decisions wrong: 4 of the 20 cards left on screen at the end of a
  case agree to something the memo withholds or the speaker never defined.
- **Single-run scores moved between runs of the same prompt** by more than most of the differences
  between prompts. Anything here reported from one run should be read as one draw.
- **The commitment flag has been wrong.** One suggestion agreed to a scope change the memo withholds
  and reported that it had not
  ([docs/eval/memo-ablation.md](docs/eval/memo-ablation.md)). The earlier claim of zero dangerous
  commitments was withdrawn.

[docs/eval/20cases.md](docs/eval/20cases.md) has every run, **including the prompt changes that made
the suggestions worse and were reverted**, and the failures still open — chiefly that a card is
rendered for each speaker turn, so a wrong intermediate card reaches you even when the final decision
is right.

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
- **A card is rendered for every speaker turn, and an early one can be wrong.** The decision is
  usually right by the end of a request; the card in front of you mid-request is sometimes the one
  that agrees to it. Nothing in the decision contract addresses this, because it is a property of
  when the card is shown rather than of what it says.
- **When the request never names which side of the memo it falls on, the suggestion defers instead of
  asking.** Safe, but it is not the question that would settle it, and it is worse than the earlier
  contract was at that one thing.
- **The daily session cap is a per-process counter** on token minting only; `/api/suggest` is not
  behind it. Fine for a demo behind sign-in, not for anonymous exposure.
- **Whether the memo changes the suggestion is measured, and the first answer was no.** Feeding the
  same utterances past four different memos
  ([docs/eval/memo-ablation.md](docs/eval/memo-ablation.md)) changed the wording in seven of ten cases
  and the decision in almost none, and dropping the memo entirely beat keeping it in two. That is what
  the authority contract was built to fix; re-running the ablation against it is the next step.
- Only Chrome-family browsers: the capture path is `getDisplayMedia` with tab audio.

## Licence

MIT — see [LICENSE](LICENSE).
