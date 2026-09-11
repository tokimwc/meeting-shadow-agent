# Submission text

## Title

Meeting Shadow Agent

## Short description

Watches an English meeting you are in and hands you the one line to say before you agree to something
you cannot approve.

## Long description

A Japanese engineer on an English delivery call understands every word and still says yes too early.
Not from a language gap — from the speed of it. Which environment, whose approval, by when, at what
effort: four conditions that were never settled, and a "sure, Friday works" that costs three weeks.

Meeting Shadow Agent listens to the other participants and, at the end of each of their turns,
proposes one English sentence for the engineer to say. It never speaks, never joins the call, never
sends anything. The engineer reads the card and decides.

What makes the suggestion usable is a short memo the engineer writes before the meeting, naming what
they may settle alone and what they may not. A request that falls inside that authority gets a
sentence that commits. A request outside it gets a sentence that defers, naming the specific thing
that needs internal approval — not a generic "let me get back to you".

**How it is built.** Chrome tab audio (`getDisplayMedia`) goes straight from the browser to
AssemblyAI Universal-3.5 Pro Realtime over WebSocket, using a one-time token; the server never holds
the stream. Each finalized turn goes to Gemini 2.5 Flash-Lite under a JSON schema that forces every
claim to cite the utterance ids behind it. A suggestion citing an id that was never spoken is refused
rather than repaired, and an open item whose only evidence is the engineer's own memo is dropped —
the memo says what needs approval, it is not evidence that anyone asked for it. Deployed on Cloud
Run behind IAP.

**What was measured.** Twenty scripted scenarios — twelve synthetic-audio, eight human-recorded —
crossing five conditions (environment, deadline, scope, authority, effort) with four situations:
a condition left undefined, a condition the speaker revises mid-sentence, a request that conflicts
with the memo, and a conversation where everything is already settled. Median 1.9 s from end of
speech to card, p90 2.4 s. Zero dangerous commitments and zero invalid evidence ids across four full
runs.

**What it does not show.** This is a developer-authored test suite, not a field study. Zero failures
in twenty trials leaves a one-sided 95% upper bound near 14%, and scenarios built by the person
building the agent do not generalise to real meetings. The evaluation note in the repository records
every run, including the two prompt changes that made things worse and were reverted, and the case
where a non-native reading of "Oh, and the database schema change goes with it" reached the model as
"Oh. End of day. Cause visit." — the words a decision turns on are exactly the ones an accent puts at
risk.

The agent's job is to be ready with the sentence. Saying it is still the engineer's.

## Tags

assemblyai, realtime-stt, universal-3, gemini, voice-agent, meetings, google-meet, non-native-english,
decision-support, cloud-run

## Cover image

One frame: a Google Meet window with a suggestion card beside it, the card reading a conditional
English sentence. No faces, no logos beyond the ones we are entitled to use, no stock "AI brain".
