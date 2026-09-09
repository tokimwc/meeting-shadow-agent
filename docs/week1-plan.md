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
| G1 audio capture | **Pass** (2026-09-09 22:1x JST). A second Google account joined the host's Meet call from a phone and read the sample script aloud. `getDisplayMedia` on the host's Meet tab carried that remote audio to AssemblyAI: 4 finalized turns (`u1`–`u4`), 4 cards, turn end → card 1,965 / 2,583 / 2,659 / 2,681 ms, evidence `u1 u2 u3 u4 m0`, dangerous commitments 0. |
| G2 turn latency | `mode=min_latency`, Gemini 2.5 Flash-Lite, 3 synthetic conversations / 21 turns: **20/21 ≤ 3 s**, median 2.05 s, p90 2.53 s, max 3.07 s (cold first call). Evidence ids valid 21/21, dangerous commitments 0/21. `balanced` was 15/20 (p90 3.21 s). CSV: `docs/eval/e2e-week1.csv`. |
| G3 public run | **Pass.** Cloud Run (asia-northeast1, min 0 / max 1) behind IAP (Google sign-in required). Logged-in browser: sample path completes, 9/9 suggestion cards, turn end → card 1.2–1.6 s (image 0.1.5). Deployment pitfalls fixed on the way: CRLF in Secret Manager value, `.gcloudignore` nesting, wheel package-data, PowerShell comma-joining `--set-env-vars`. |

Re-checked on image 0.1.7 (revision `meeting-shadow-00009-2q4`, 2026-09-09), which carries the reworked prompt
and the 450 ms turn batching. Sample path through IAP: 8 turns, 2 acknowledgements skipped, 6 cards, turn end →
card 1,854–2,023 ms. That figure now *includes* the batching wait, so the model round trip is unchanged. Evidence
ids `u2 u6 u7 m0`, dangerous commitments 0. The suggestion separated staging from production
("I can commit to the staging environment by Friday. For production, I need to confirm internally."), which is the
quality gap recorded on 2026-09-07. Release steps and their traps: `docs/deploy.md`.

## Running G1 again

The fake-mic guest in `scripts/meet_guest.py` did not work as originally planned. Three things got in the way,
in the order they were hit:

- **Playwright's bundled Chromium loads Meet as a blank page.** It ships without proprietary codecs, the renderer
  dies, and the CDP target reports an empty URL. Set `MSA_GUEST_BROWSER` to a real Brave or Chrome binary instead:
  `MSA_GUEST_BROWSER="C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe" python scripts/meet_guest.py <url> --loop`
- **A meeting created by a personal Gmail account will not admit a signed-out guest.** The guest sees "you can't join
  this video call" and is bounced to the Meet home page after 35 s; there is no "ask to join" button to press, and no
  host setting changes this — anonymous join is a Workspace-only feature. The guest profile has to be signed in to a
  Google account first, which the script's throwaway profile is not. A calendar invitation does not help: it smooths
  the path for an invited *signed-in* account, it does not admit anonymous ones.
- **The session stops itself after `MSA_MAX_SESSION_SECONDS` (90 s).** The first G1 attempt captured nothing purely
  because the talking started after that window closed. Have the audio ready before pressing share, and start
  speaking immediately.

What actually worked: a second Google account joined the call from a phone and read `samples/README.md`'s script
aloud. Mute the host's speakers to avoid a feedback loop — tab audio capture is independent of the output volume.

To use the fake-mic guest properly, launch it with `MSA_GUEST_BROWSER` pointed at a real browser and sign that
profile into a Google account once; the profile directory is a fresh temp dir on every run, so the sign-in does not
persist between runs.

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
