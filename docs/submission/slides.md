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

**Title:** One sentence, ready before you need it

The other participants speak. At the end of each of their turns, a card appears with one English
sentence for the engineer to say.

It never speaks. It never joins the call. It never sends anything. The engineer reads and decides.

What it treats as still open comes from a memo written before the meeting:

> Implementation owner. Staging validation is mine to agree. Production, dates, scope changes and
> extra effort need internal approval.

Both cards on this slide are transcribed from the recorded demo — nothing composed:

| | |
|---|---|
| u1 "Can you confirm the production rollout for Friday?" | still open: **production rollout for Friday** → "Can you confirm the timezone for the production rollout on Friday?" |
| u2 "Actually I meant staging validation with no delivery commitment." | still open: **scope for staging validation** → "Could you clarify the scope for the staging validation?" |

The speaker corrects themselves and the open item moves with them: production leaves the card once it
is no longer what is being asked for.

*Visual:* the two cards side by side, the open item coloured by whether the memo places it inside the
engineer's authority.

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

## 5 — Who pays

**Title:** What one skipped conversation costs

The cost being avoided, as arithmetic rather than a claim:

| | |
|---|---|
| A scope change agreed on a call and never renegotiated | ~2 engineer-weeks |
| At a loaded cost of $100k/yr | $3,800 |
| A seat at $15/month | $180/yr — one prevented commitment covers 21 seat-years |

Market, with the cited figure and the assumed narrowing kept visibly apart:

| | | |
|---|---|---|
| Developers worldwide | **28.7 M** | 2026 estimate; SlashData counts 47 M and we use the lower one |
| *Assumed* — work in English, not natively | ≈ 14 M | Half. Our assumption. The US alone holds 4.4 M |
| *Assumed* — on external delivery calls | ≈ 2.9 M | One in five → **$520 M** serviceable against a $5.2 B total |

Revenue: per seat at $15/month, inside the $10–30 band meeting assistants already occupy; an org tier
where the memo is maintained centrally as a delegation policy. Not a revenue stream: conversations
are never resold or used to train anything of ours.

*Visual:* the dashed rules mark the two rungs that are assumptions, so a judge can see at a glance
which number is cited and which is ours.

---

## 6 — Where this sits

**Title:** Evidence grounding is not the differentiator

Four agents in this same hackathon already tie their output back to what was said — VerbaTrace AI,
QuoteReady, Voice Action Gate, Saakshi. Naming them is the point: the category is crowded and
pretending otherwise would be the easiest thing for a judge to check.

Every one of them **acts** — questions the other party, writes a record, or blocks a call. This one
does not. It prepares **the user's own next sentence**, shaped by a boundary the user declared before
the meeting, and hands it over to be said or discarded.

Stated plainly: neither evidence grounding nor latency is a moat. What is defensible is the authority
memo as the shaping input, and the discipline of never acting.

*Visual:* the competitor list in mono, the differentiator in the one colour the deck reserves for
what the engineer may settle.

---

## 7 — What it does not show

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
