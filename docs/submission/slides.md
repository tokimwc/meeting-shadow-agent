# Seven slides

The judges watch the video first and open the deck to check what the video claimed, so each slide
answers one question a sceptic would ask. Slides 5 and 6 exist because the submission guidelines ask
for market scope, revenue and a competitor analysis, and Business Value is one of the four judging
axes the first draft left empty.

---

## 1 — The problem

**Title:** Understanding every word is not the problem

An engineer on an English delivery call follows the meeting fine. What goes wrong is the speed: the
other side asks, and the answer lands before four conditions have been checked.

| | |
|---|---|
| Environment | staging or production? |
| Deadline | which date, in whose timezone? |
| Scope | what is in, what is explicitly out? |
| Authority | whose approval does this actually need? |

The cost does not appear in the meeting. It appears three weeks later.

*Visual:* the four conditions as a row, greyed; one of them lit.

---

## 2 — What it does

**Title:** A reply, and whose decision it is

After each turn of the other side, a card names what is asked and whose call it is, then suggests a
reply. Simulated client (Gemini 2.5 Flash), TTS voices. The memo written before the meeting:

> Implementation owner. Staging validation is mine to agree. Production, dates, scope changes and
> extra effort need internal approval.

One card, transcribed from the recorded demo:

- u2 "Can you confirm that the fix will go live in production on Friday?"
- production on Friday · **needs internal approval** → "I need to confirm internally about the
  production release on Friday. I will get back to you." (cites u2 · m0, suggestion call 1,339 ms)

The engineer reads it and decides. Nothing is spoken or sent. The client's pushback on the next turn
is in the video, not on the slide.

---

## 3 — How it is built

**Title:** Our server never receives the audio

```
Chrome tab audio ──WebSocket, one-time token──▶ AssemblyAI Universal-3.5 Pro Realtime
                                                          │  finalized turn
                                                          ▼
                              Cloud Run (IAP) ──▶ Gemini 2.5 Flash-Lite ──▶ card
```

Two guards, both refusals rather than repairs:

- Every claim cites the utterance ids behind it. A suggestion citing an id nobody spoke is rejected.
  The check is that the id exists, not that it supports the reply.
- An open item whose only evidence is the engineer's own memo is dropped. The memo says what needs
  approval; it is not evidence that anyone asked for it.

*Visual:* the diagram above, drawn properly. Keep the arrows honest — the audio does not pass
through the server.

---

## 4 — What was measured

**Title:** The memo moves the decision. Measured by moving the memo.

The claim is that the memo, not the model's caution, decides. So the same utterances were put past
four different memos. The five cases that ask for staging-only things — which the shipped memo grants
and a narrower memo withholds:

| Case | Memo grants staging | Memo withholds it |
|---|---|---|
| delivery date already approved | mine to agree | **needs approval** |
| scope is the two endpoints | mine to agree | **needs approval** |
| go-ahead for the staging run | mine to agree | **needs approval** |

Three of five flipped on the same words (one text-only run); of the other two, one returned no card
and one did not move. Repeating one configuration instead of running it once, and scoring the decision
label rather than the sentence: when the memo grants what is asked, 15 of 15 calls labelled it `mine`;
when it withholds, 13 of 15 labelled it `needs_approval` (one `unclear`, one provider error). Beside
them, the failure: in the audio run, 4 of 20 final cards agree to something the memo withholds or the
speaker never defined.

58 of 62 turns returned a suggestion; median 2.02 s end of speech → suggestion generated, p90 2.55 s, in-process.

*Visual:* the shipped-vs-narrow table above, and beside it the run table from `docs/eval/20cases.md`
including the runs that scored worse.

---

## 5 — Who it is for

**Title:** The engineer feels it. The delivery lead pays for it.

A hypothesis, not yet tested with buyers:

- **Uses it:** a Japanese-speaking engineer on English client calls, who follows the request but cannot
  approve dates, production or scope.
- **Pays for it:** the delivery lead at a software services firm, who absorbs the unpaid rework when a
  quick yes becomes a commitment.
- **Has to allow it:** information security — client audio goes to AssemblyAI, the text and the memo to
  Gemini.

Price hypothesis: $15 per seat per month. Willingness to pay, usage cost and avoided rework have not
been measured. The market-size arithmetic of the earlier deck was removed: it jumped from developer
headcount to buyers without evidence for either step.

---

## 6 — What it is up against

**Title:** What the engineer could use instead

| Instead | What it gives | What it misses |
|---|---|---|
| "Let me check and get back to you" | Safe, instant, free | Defers what the engineer may agree to as well |
| The memo, kept beside the call | The boundary in view | Matching it to the request, in English, mid-call |
| Copilot in Teams · Ask Gemini in Meet | Private answers about the meeting | Waits to be asked; Copilot only in meetings your own organisation hosts |
| **This agent** | A reply shaped by the boundary the engineer declared, after every turn of the other side | |

Not yet measured: whether engineers prefer it to any of the three.

Sources for row 3: Microsoft Support, "Frequently asked questions about Copilot in Microsoft Teams" and
Microsoft Q&A on externally hosted meetings; Google Meet Help, "Ask Gemini in Google Meet".

---

## 7 — What it does not show

**Title:** Three limits, and the check each needs next

- **Wrong agreements.** In the audio run, 4 of 20 final cards agree to what the memo withholds or never
  defined, and the model's own commitment flag has been wrong once. *Next: score every card, not only
  the last.*
- **Old question.** When the client changes the question after a refusal, the card can keep deferring
  on the old one. *Next: test a fix against a model client that argues back.*
- **Not tried live.** The cases were written by the builder, and no engineer has read a card during a
  live call. *Next: mock calls against a memorised line and a memo on paper.*

Latency, accent errors, retention and reverted prompts are in `docs/eval` and the README.
