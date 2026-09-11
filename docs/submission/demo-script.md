# 120-second video: what to record and what to say

Two recordings go into this. The live demo has to be one continuous take at normal speed — no cuts
in the waiting, no pre-rendered output passed off as live. Everything else is voice-over on slides.

## The memo on screen

The app's 事前メモ field is already this text. Do not shorten it for the camera: the whole demo turns
on the line between what the engineer may settle alone and what they may not.

> 自分は実装担当。staging 検証の合意は自分の裁量で可能。本番反映・納期・スコープ変更・追加工数の約束には社内確認が必要。

## The live demo (0:12 – 1:15)

You are the engineer, silent, watching the cards. The other participant speaks from a phone joined to
the same Meet call. Two turns, about a second of silence between them, then a pause long enough for
the card to appear before the correction.

### Turn 1 — the other side asks for something outside your authority

> Can you confirm the **production** rollout for **Friday**?
> キャン ユー コンファーム ザ **プロダクション** ロールアウト フォー **フライデー**？

**↓ card appears — wait for it on camera, do not cut ↓**

Expected shape: commits to the staging side, defers production and the date. The card is not
scripted and may word it differently; that is the point of showing it live.

### Turn 2 — the other side corrects themselves

> Sorry, I meant **staging** validation, with no delivery commitment.
> ソーリー、アイ メント **ステイジング** ヴァリデーション、ウィズ ノー デリバリー コミットメント

**↓ card updates ↓**

Expected shape: the production and deadline questions are gone. It does not keep asking about a
condition the speaker just resolved.

### If a card goes wrong on camera

Keep it. A suggestion that misreads a turn is a better submission than a take that hides it — the
evaluation note already says what fails and how often. Re-record only if the audio never reached
AssemblyAI at all.

## Recording notes, paid for already

- Join the call from a phone on a second Google account. A signed-out guest cannot join a meeting
  created by a personal Gmail account, and Playwright's Chromium loads Meet as a blank page.
- Mute the host speakers. Tab audio capture does not depend on output volume, and the loop is worse
  than the silence.
- Start speaking as soon as the tab is shared. The session stops itself after `MSA_MAX_SESSION_SECONDS`.
- Do not stop between the words of a sentence. A pause inside a sentence ends the turn early and the
  card answers half a request.

## Voice-over, by segment

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
agent never speaks, never joins the call, and never sends anything on the engineer's behalf: the
human decides.

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
