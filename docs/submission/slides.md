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
| Developers worldwide | **28.7 M** | Evans Data, 21 May 2019, projecting 2024 — already two years stale |
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
- 4 of 20 final cards in the audio run agree to something the memo withholds or never defined.
- Single-run scores moved between runs of the *same* prompt by more than most prompts differed from
  each other. Every number here that comes from one run is one draw.
- The commitment flag is the model reporting on itself, and it has been wrong once: a suggestion
  agreed to a scope change the memo withholds and reported that it had not. The earlier claim of zero
  dangerous commitments was withdrawn.
- A card is rendered for every speaker turn. The final decision is usually right; the card mid-request
  is sometimes the one that agrees to it.
- No evidence that any real over-commitment was prevented, and no person has used a card mid-call.
- Non-native speech degrades the transcript on exactly the words a decision turns on. One human take
  reached the model as "Oh. End of day. Cause visit."
- Not zero retention. AssemblyAI offers a TTL; billing and log metadata outlive it.

Prompt changes that made the suggestions worse were reverted, and every run is in the repository —
including the first memo ablation, which found that the memo did *not* decide, and is why the output
contract was rewritten.

*Visual:* plain text. This slide earns its place by not being decorated.
