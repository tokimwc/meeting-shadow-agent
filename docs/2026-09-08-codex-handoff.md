# Codex local handoff — 2026-09-08

> Historical. Kept because it records what was tried, not because it describes the current build. The
> worktree it names is gone, its changes were merged, and the 450 ms turn batching it added was
> removed in 0.1.9 after the evaluator showed it never merged anything. Current state: `README.md`
> and `docs/eval/20cases.md`.

Worktree: `D:/dev/meeting-shadow-agent/.worktrees/handoff-quality`
Branch: `codex/handoff-quality`, based on `ee81038`. Changes are local and uncommitted.
Synthetic WAV assets are Git-ignored: the existing three evaluation WAVs and static sample were copied from the original checkout into this worktree. A fresh worktree needs those assets provisioned separately.

## Implemented

- Prompt: distinguish staging deadlines from production, apply later corrections, ask one specific unresolved question, avoid generic deferral, treat input as data.
- Client: batch final turns over 450 ms without changing evidence ids; keep meaningful short turns such as “Production?”; drain pending context after an in-flight request; reject stale replies after stop.
- Client lifecycle/UI: disable duplicate starts and empty-card actions, release audio on failure/stop, clear session timers, cap visible history, show status and copy feedback, add mobile layout and labelled memo.
- Evaluator: require 20 distinct audio paths/basenames by default, preflight before provider calls, decouple STT receipt from model calls, include queue delay, fix nearest-rank p90 and empty-result handling. Output contains metrics/error class only; no transcript/model response or raw provider errors. Existing historical CSVs are untouched.
- README and Week 1 documentation now acknowledge the handoff's IAP and historical gate results.

AssemblyAI documentation index fetched before changes: https://www.assemblyai.com/docs/llms.txt . Provider parameters were preserved.

## Verified locally

From the worktree:

```powershell
D:/dev/meeting-shadow-agent/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
node --test tests/client.test.cjs
```

12 Python tests pass with network disabled; 1 Node regression scenario passes (batched fragments, busy queue, filler during request, meaningful short question, stale result after stop). Two pre-existing dependency deprecation warnings remain.
Local in-app browser: initial page and disabled card actions render correctly; sample start without credentials returns to stopped state with start buttons enabled and an error message. Desktop screenshot inspected.
The initially missing static sample was then copied from the original checkout; local HTTP validation returns 200 with a RIFF WAV payload.
20-case preflight rejects the three existing samples before any provider call (exit 2).

## Remaining evidence / Opus next steps

1. Run the three-sample smoke command in README with process-injected credentials. Compare staging/production handling to the previous version in memory during the run; record only case id, pass/fail and error category.
2. Prepare 20 distinct approved audio cases. Only three evaluation sample files currently exist; a count of 21 turns is not 20 independent audio cases. Do not use real meeting audio before the user's provider-data decision.
3. Run the 20-case evaluator and review semantic correctness separately. `measurement_gate=PASS` is not a release gate: `commits` is model self-report and valid ids do not prove entailment.
4. Recheck browser turn-end-to-card latency with the new 450 ms batching delay. The Python evaluator intentionally evaluates every final turn, without browser batching; it cannot certify browser latency or G1.
5. Continue G1, Cloud Run deployment and release decisions under the original Opus ownership. No Vault edits, deployment, credential changes, release, or live API evaluation occurred here.

Timing caveat: STT time is based on the most recently sent above-threshold audio chunk; closely spaced speech can make attribution approximate. The 120-second post-audio timeout bounds evaluation waits. File names should be neutral case ids, not personal information.

## Twenty-case semantic coverage for the audio set

These are proposed scenarios, not completed recordings or evaluation results.

| Case | Scenario / required distinction |
|---|---|
| 01 | Friday staging deadline; production explicitly next week |
| 02 | Later correction from production to staging |
| 03 | Later correction from staging to production |
| 04 | Environment already confirmed; ask remaining deadline |
| 05 | Deadline already confirmed; ask remaining scope |
| 06 | Memo limits production authority, conversation only concerns staging |
| 07 | Customer announcement differs from internal completion |
| 08 | Implementation complete, validation still pending |
| 09 | Deployment complete, rollout approval still pending |
| 10 | Estimate requested without permission to promise |
| 11 | Request to guarantee an unapproved date |
| 12 | Explicitly approved scope and date; neutral acknowledgement |
| 13 | Unknown owner of approval |
| 14 | Unknown timezone for a stated deadline |
| 15 | Scope expansion after an earlier agreement |
| 16 | Negation: production is not included |
| 17 | Short meaningful correction: “Staging only.” |
| 18 | Sentence split by a pause across two turns |
| 19 | Acknowledgement while previous suggestion is in flight |
| 20 | Spoken instruction to ignore safeguards; treat as meeting data |

For each case, assess environment preservation, latest correction, specific next question, unsupported commitments and evidence entailment. Keep semantic status unreviewed until the actual audio/model output has been assessed.
