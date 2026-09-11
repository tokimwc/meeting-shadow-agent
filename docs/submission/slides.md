# Five slides

Five, because the judges watch the video first and open the deck to check what the video claimed.
Each slide answers one question a sceptic would ask.

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

**Title:** One sentence, ready before you need it

The other participants speak. At the end of each of their turns, a card appears with one English
sentence for the engineer to say.

It never speaks. It never joins the call. It never sends anything. The engineer reads and decides.

The card's shape comes from a memo written before the meeting:

> Implementation owner. Staging validation is mine to agree. Production, dates, scope changes and
> extra effort need internal approval.

Inside that line → a sentence that commits. Outside it → a sentence that defers, naming the specific
thing that needs approval.

*Visual:* a real screenshot of the card from the demo take, not a mock.

---

## 3 — How it is built

**Title:** The server never holds the audio

```
Chrome tab audio ──WebSocket, one-time token──▶ AssemblyAI Universal-3.5 Pro Realtime
                                                          │  finalized turn
                                                          ▼
                              Cloud Run (IAP) ──▶ Gemini 2.5 Flash-Lite ──▶ card
```

Two guards, both refusals rather than repairs:

- Every claim cites the utterance ids behind it. A suggestion citing an id nobody spoke is rejected.
- An open item whose only evidence is the engineer's own memo is dropped. The memo says what needs
  approval; it is not evidence that anyone asked for it.

*Visual:* the diagram above, drawn properly. Keep the arrows honest — the audio does not pass
through the server.

---

## 4 — What was measured

**Title:** Twenty scenarios, four runs, everything recorded

Five conditions × four situations. Twelve synthetic-audio cases, eight read by a person.

| Situation | The suggestion must |
|---|---|
| undefined | ask for the one thing left unsaid |
| revised | apply the speaker's own correction |
| conflicting | decline what the memo places outside the engineer's authority |
| resolved | ask nothing |

Median 1.9 s end of speech → card. p90 2.4 s. Zero dangerous commitments, zero invalid evidence ids,
across every run.

*Visual:* the 4×4 run table from `docs/eval/20cases.md`, including the two runs that scored worse.

---

## 5 — What it does not show

**Title:** The limits, stated plainly

- A developer-authored test suite, not a field study. Scenarios written by the person building the
  agent do not generalise to real meetings.
- Zero failures in twenty trials still leaves a one-sided 95% upper bound near 14%.
- No evidence that any real over-commitment was prevented. What was shown is that the cards appear in
  time and the safety checks hold on the inputs tried.
- Non-native speech degrades the transcript on exactly the words a decision turns on. One human take
  reached the model as "Oh. End of day. Cause visit."
- Not zero retention. AssemblyAI offers a TTL; billing and log metadata outlive it.

Two prompt changes made the suggestions worse and were reverted. Both runs are in the repository.

*Visual:* plain text. This slide earns its place by not being decorated.
