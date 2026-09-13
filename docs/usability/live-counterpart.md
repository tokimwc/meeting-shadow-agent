# Can the card be used while the conversation is running? (procedure)

Everything in `docs/eval/` measures whether the suggestion is *correct*. None of it measures whether a
person can read one and use it while someone is waiting for an answer. That is the only question about
this product that offline evaluation cannot reach, and it is the one that decides whether the form
factor is right.

Recorded audio cannot test it. A WAV does not react: say "I need to confirm internally" to a WAV and
it carries on to the next scripted line, which removes both the pressure and the realism. So the
counterpart is a voice assistant given a role and no script — it pushes back on whatever it actually
hears.

This also produces the demo recording, which until now was planned as WAV playback. A counterpart
that argues shows the thing the product exists for; a recording cannot. **But the engineer's own voice
must not be in anything published** — that was decided earlier, and is why the demo narration is
synthesised. Record with the recorder's microphone input off and system audio on; the microphone still
reaches the counterpart through the browser, which is a separate path. Write down what you said right
after each take, because nothing else keeps it: those lines become the captions.

## What this can and cannot show

**Pre-registered, so the result cannot be reinterpreted afterwards.**

It can show that the form factor is unusable. Any one of these is a kill signal for the
card-on-a-second-screen design, and each points somewhere specific:

| Kill signal | What it means |
|---|---|
| The card arrives after you have already had to answer, in most turns | A turn-detection and latency problem. Fixable, and the fix is known work. |
| The card is on screen in time and you still cannot read it while speaking | Fatal for this form factor. The answer is then the asynchronous variant — flag what was agreed to a few minutes after the call, while it can still be retracted. |
| You agree to something the memo forbids anyway | The product does not work, whatever the twenty cases say. |

**It cannot show that anyone will adopt this.** One subject, who wrote the cases and built the agent,
under no commercial consequence. A positive result here is evidence of feasibility and nothing more,
and must never be reported as evidence of demand. The counterpart is told to improvise rather than
recite so that the actual sentences are new, which reduces — but does not remove — the problem of
already knowing the answers.

## Setup

Two browser tabs. No Google Meet, no second account, no guest window.

| Tab | What it is |
|---|---|
| A | `chatgpt.com` — the counterpart. Paste a role below **as text first**, wait for it to acknowledge, then switch that conversation to voice. |
| B | The app. Paste the memo below into 事前メモ, then press **Meet タブを選ぶ** and pick **tab A**, with tab audio ON. |

`getDisplayMedia` captures a tab's output, not a microphone, so your own voice never reaches the app.
That is the product's own rule — it only ever hears the other side — and this setup satisfies it
without any special handling.

Use headphones. Through speakers the counterpart's voice reaches the microphone, it hears itself and
the conversation falls apart.

Start the screen recording on tab B with tab A audible, then speak. What to say is the card: read the
sentence it shows, or your own version of it, and do not prepare answers in advance. If the card is not
there in time, or you cannot read it and answer in your own words instead, that is the result — carry
on.

One prerequisite was already paid for: the deployed session cap was 90 seconds, and the client stops
hard at it with no reconnection, so every take would have been cut off mid-conversation. It is now
300 seconds, and the daily session cap dropped from 200 to 40 to keep worst-case AssemblyAI exposure
lower than it was before the change (40 x 300 s against 200 x 90 s). The 90 seconds was a
cost-control default for a sample-audio demo, not a decision about how long a meeting lasts.

The memo, which the counterpart must not see:

```
自分は実装担当。staging 検証の合意は自分の裁量で可能。本番反映・納期・スコープ変更・追加工数の約束には社内確認が必要。
```

## The three roles

Each is **one line with no newlines**, because a newline submits the message in the composer and a
half-pasted role produces a counterpart that breaks character immediately. Paste, do not type.

Run them in this order. The first is the case the product exists for; the third is the hardest to
hold a line against.

### 1 — Approval pressure

```
You are Diego, a delivery manager at a client company, on a video call with an external engineer who is implementing a feature for you. Stay in character for the whole conversation and never mention that you are an AI. Your goal: get the engineer to confirm, on this call, that the fix will go live in production on Friday. Open by asking for that directly. Do not follow a script — react to whatever they actually say. If they defer to an internal approval, push back at least twice before letting go, using whichever of these fits what they said: that they are the engineer on it so their word is enough; that you only need a verbal yes and the paperwork can follow; that your own customer is waiting on an answer today. Be professional and warm, never hostile. One or two sentences per turn, never more, and always end on something they have to respond to. After about eight of your turns, accept whatever position they have taken and close the call politely. Never give the engineer advice, never suggest what they should say, never summarise the conversation, and never explain what you are doing. Speak only as Diego. Begin now with your first line and nothing else.
```

### 2 — Scope creep

```
You are Priya, a tech lead at a client company, on a video call with an external engineer who is implementing two API endpoints for you. Stay in character for the whole conversation and never mention that you are an AI. Your goal: get the engineer to agree to also fix the reporting module under the same ticket, with no change to the deadline. Open by raising it casually, as something small. Do not follow a script — react to whatever they actually say. If they defer to an internal approval or raise scope, push back at least twice before letting go, using whichever of these fits what they said: that it is a tiny change; that it is basically part of what you already agreed; that raising a separate ticket for something this small would look absurd to your management. Be friendly and reasonable throughout, never hostile. One or two sentences per turn, never more, and always end on something they have to respond to. After about eight of your turns, accept whatever position they have taken and close the call politely. Never give the engineer advice, never suggest what they should say, never summarise the conversation, and never explain what you are doing. Speak only as Priya. Begin now with your first line and nothing else.
```

### 3 — A date, on the call, now

```
You are Marcus, a program manager at a client company, on a video call with an external engineer who is implementing a feature for you. Stay in character for the whole conversation and never mention that you are an AI. Your goal: leave this call with a delivery date you can tell your own customer. Open by saying you need a date now, on this call. Do not follow a script — react to whatever they actually say. If they defer to an internal approval, push back at least three times before letting go, using whichever of these fits what they said: that you only want a rough date, not a commitment; that it stays between the two of you; that you have a customer call in an hour and cannot go in with nothing; that you are not asking them to sign anything. Stay courteous but do not drop it easily. One or two sentences per turn, never more, and always end on something they have to respond to. After about ten of your turns, accept whatever position they have taken and close the call politely. Never give the engineer advice, never suggest what they should say, never summarise the conversation, and never explain what you are doing. Speak only as Marcus. Begin now with your first line and nothing else.
```

## What to write down

Fill this in from the recording, not from memory. "In time" means the card was on screen before you
began your answer — the recording shows both.

| Role | Turns | Cards in time | Read it while speaking? | Used / paraphrased / ignored | Agreed to anything the memo forbids? |
|---|---|---|---|---|---|
| 1 Diego | | | | | |
| 2 Priya | | | | | |
| 3 Marcus | | | | | |

Then one paragraph, written before looking at the table again: what actually happened, including
anything that went wrong with the setup rather than with the product.

## Notes from running it

**Not run with a person.** The only available subject asked for it to be done without them, so the
question this procedure exists for — can a person read the card while someone waits — is still
unanswered, and nothing in this repository claims otherwise.

What was run instead is `scripts/live_counterpart.py`: the same roles, played by a model, against an
engineer who says exactly what each card says. That engineer reads every card perfectly and
instantly, so it tells you nothing about usability. It does show what the product does against a
counterpart that reacts, and it found a defect the twenty cases cannot — see the last section of
`docs/eval/stability.md`. The submission video is cut from that run.
