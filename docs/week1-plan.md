# Week 1 (2026-09-08 – 09-14): 4 hours, go/no-go

Goal: a public URL where Meet-tab audio (or the sample clip) → AssemblyAI → Gemini → one suggestion card works,
and the latency gate is measured on real audio.

## Gates (from the strategy note; numbers are targets, not results)

| Gate | Pass condition | If it fails |
|---|---|---|
| G1 audio capture | `getDisplayMedia({video:true, audio:true})` on a Google Meet tab in Chrome/Windows yields an audio track carrying the *remote* participants | Try Zoom web client once. If neither works, withdraw from plan A. |
| G2 turn latency | Turn end (`end_of_turn && turn_is_formatted`) → card rendered ≤ 3 s in 18/20 short exchanges | Tune `mode` first; then model (`gemini-2.5-flash-lite` → alternative); then withdraw. |
| G3 public run | Same flow works from Cloud Run URL with IAP Google sign-in, no key entry, no mic permission for the sample path | Fix before adding any feature. |

## Results so far (2026-09-09)

| Gate | Result |
|---|---|
| G1 audio capture | Browser sample path works (AudioWorklet → AAI). Meet tab capture **not yet tested** on a real call. |
| G2 turn latency | `mode=min_latency`, Gemini 2.5 Flash-Lite, 3 synthetic conversations / 21 turns: **20/21 ≤ 3 s**, median 2.05 s, p90 2.53 s, max 3.07 s (cold first call). Evidence ids valid 21/21, dangerous commitments 0/21. `balanced` was 15/20 (p90 3.21 s). CSV: `docs/eval/e2e-week1.csv`. |
| G3 public run | **Pass.** Cloud Run (asia-northeast1, min 0 / max 1) behind IAP (Google sign-in required). Logged-in browser: sample path completes, 9/9 suggestion cards, turn end → card 1.2–1.6 s (image 0.1.5). Deployment pitfalls fixed on the way: CRLF in Secret Manager value, `.gcloudignore` nesting, wheel package-data, PowerShell comma-joining `--set-env-vars`. |

Re-checked on image 0.1.7 (revision `meeting-shadow-00009-2q4`, 2026-09-09), which carries the reworked prompt
and the 450 ms turn batching. Sample path through IAP: 8 turns, 2 acknowledgements skipped, 6 cards, turn end →
card 1,854–2,023 ms. That figure now *includes* the batching wait, so the model round trip is unchanged. Evidence
ids `u2 u6 u7 m0`, dangerous commitments 0. The suggestion separated staging from production
("I can commit to the staging environment by Friday. For production, I need to confirm internally."), which is the
quality gap recorded on 2026-09-07. Release steps and their traps: `docs/deploy.md`.

## Task list (owner in brackets)

1. [user] AssemblyAI sign-up via the hackathon credit link; put the key in 1Password (`OpenClaw Runtime` or a new item). Confirm granted credit amount and the data-retention / training opt-out setting in the dashboard.
2. [claude] `op run` wrapper `.env.op` (op:// references only) and a local smoke run of `/api/token` (expect 200 and a one-time token).
3. [claude] Sample conversation audio `samples/sample-01.wav`: 4 English lines by a synthetic voice (no real person), ~40 s. Script kept in `samples/README.md`.
4. [user+claude] G1 test on a real Meet call (a second account or a colleague who consents). Measure whether remote audio appears in the tab stream.
5. [claude] 20-case latency run with the sample clip variants; record `turn end → card` per case in `docs/eval/week1-latency.csv`.
6. [claude] Cloud Run deploy to a *new* project (not the CutFlow one): min 0 / max 1, secrets via Secret Manager, `MSA_DAILY_SESSION_CAP=200`. Verify `/health` and the sample path from a logged-in browser.
7. [user] Decision at 09/14: continue A, or withdraw per the gates above.

## Not in week 1

TTS, auto-speak, Zoom native, Chrome extension, speaker labels, transcripts export, multi-agent, character assets.
