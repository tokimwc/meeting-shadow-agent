# 120-second video: what to record and what to say

No human voice goes into this. The remote participant is a synthetic voice played into the call
through a fake microphone; the narration is separate. The demo itself stays live — tab audio,
AssemblyAI and Gemini all run for real, in one continuous take at normal speed.

Say so once in the video or its description: **the remote participant is a synthetic voice.** The
product's behaviour is real and nothing is staged, but a viewer should not have to guess whether a
second person was in the room.

## The memo on screen

The app's 事前メモ field already holds this text. Do not shorten it for the camera: the whole demo
turns on the line between what the engineer may settle alone and what they may not.

> 自分は実装担当。staging 検証の合意は自分の裁量で可能。本番反映・納期・スコープ変更・追加工数の約束には社内確認が必要。

## The two turns

Rendered by `python scripts/make_cases.py --demo` into `samples/demo-lines.wav`. Both turns were
verified through AssemblyAI first and come back verbatim, as one turn each.

| | |
|---|---|
| 0:05 | "Can you confirm the **production** rollout for **Friday**?" |
| | *eight seconds of silence — the card appears and is readable on camera* |
| 0:22 | "Actually I meant **staging** validation with no delivery commitment." |
| | *the card updates* |

The first card should commit to the staging side and defer production and the date. The second should
drop the questions the first raised, because the speaker resolved them. Neither is scripted — that is
the point of showing it live.

## Running it

The guest is a real Brave window whose microphone is the WAV. Playwright's own Chromium loads Meet as
a blank page, so the override is not optional.

```
set MSA_GUEST_BROWSER=C:\Program Files\BraveSoftware\Brave-Browser\Applicationrave.exe
python scripts/meet_guest.py <meet-url> --wav samples/demo-lines.wav --profile .cache/meet-guest
```

`--profile` keeps the guest's browser profile between runs. Sign that window into the second Google
account **once**: a meeting created by a personal Gmail account will not admit a signed-out guest,
and without `--profile` every run starts signed out again.

Audio starts five seconds after the mic opens. Have the Meet tab already shared before then — the
session stops itself after `MSA_MAX_SESSION_SECONDS`.

Mute the host speakers. Tab audio capture does not depend on output volume, and the loop is worse
than the silence.

## If a card goes wrong on camera

Keep it. A suggestion that misreads a turn is a better submission than a take that hides it — the
evaluation note already records what fails and how often. Re-record only if the audio never reached
AssemblyAI at all.

## Narration, by segment

Synthesised or on-screen text, not a live read.

**0:00 – 0:12 — the problem**
An engineer in an English meeting understands every word and still says yes before the conditions are
sorted: which environment, whose approval, by when, at what effort. The cost lands weeks later.

**0:12 – 1:15 — the demo**
Narrate only what is on screen. Name the moment the card separates staging from production, and the
moment the correction clears the questions it had raised.

**1:15 – 1:35 — how it works**
Tab audio goes straight from the browser to AssemblyAI Universal-3.5 Pro Realtime over WebSocket; the
server never holds the stream. Each finalized turn goes to Gemini 2.5 Flash-Lite, which must cite the
utterance ids it used. A suggestion citing an id that was never said is refused, not repaired. The
agent never speaks, never joins the call, and never sends anything on the engineer's behalf.

**1:35 – 1:50 — what was measured**
Twenty scripted scenarios, twelve synthetic-audio and eight human-recorded, across missing, revised,
conflicting and resolved conditions. Median 1.9 s from end of speech to card, p90 2.4 s. Zero
dangerous commitments and zero invalid evidence ids across every run. State plainly: this is a
developer-authored test suite, not a field study, and zero failures in twenty trials still leaves a
one-sided 95% upper bound near 14%.

**1:50 – 2:00 — who it is for and where to try it**
Non-native engineers on English delivery calls. Live demo behind a Google sign-in; the recorded
replay needs no account.

## Lines not to say

- "Complete zero retention." AssemblyAI offers a TTL, and billing and log metadata outlive it.
- Browser-reported latency as if it were the gate figure. The browser clock starts when the finalized
  turn arrives, not when the speaker stops. Only `scripts/e2e_eval.py` measures end of speech → card.
- "It prevents over-commitment." Nothing measured here shows a commitment that did not happen.
