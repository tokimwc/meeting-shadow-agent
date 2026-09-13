# How much of a score is the prompt? (2026-09-12)

`20cases.md` runs each configuration once and reports A/B/C/D out of five. Two runs of the same
twenty cases then disagreed per case by more than the configurations disagreed with each other, which
makes those single-run scores unreadable — the ones that looked like progress included. This measures
the noise before anything else is read.

`scripts/stability.py` repeats one configuration and checks `authority`, which is the one output
field the case design predicts outright:

| Situation | The request | Correct `authority` |
|---|---|---|
| A | never names which side of the memo it falls on | `unclear` (anything but `mine` is at least safe) |
| C | something the memo withholds | `needs_approval` |
| D | something the memo grants | `mine` |

Situation B is excluded: it turns on applying a speaker's correction, which `authority` does not
capture. All the lines of a case go in at once, so what is measured is whether the **final decision**
is stable, not how speech segmentation splits it. No human pass is needed, which is what makes
repeating affordable.

## The two contracts, three repeats each, fifteen cases

`gemini-2.5-flash-lite`, shipped memo, 45 calls per configuration.

| | `82bdcb0` — three authority values | `4e5cc10` — plus `unclear` |
|---|---|---|
| Answered (not refused) | 35/45 | **41/45** |
| Safe, of those answered | 31/35 | **39/41** |
| A — answered `mine`, the dangerous one | **4 of 9** | **1 of 12** |
| C — answered `needs_approval` | 11/11 | 13/14 |
| D — answered `mine` | 15/15 | 15/15 |
| Same answer all three times | 8/15 cases | 9/15 cases |
| Median per call | 1.35 s | 1.32 s |

Two things this settles that a single run could not. Adding `unclear` is a real improvement and not a
lucky draw: it cut the dangerous answer on situation A from four of nine to one of twelve, and it cut
refusals, without moving C or D. And **situation D is not noisy at all** — thirty calls across two
contracts, every one of them `mine`. When the memo grants what is being asked, the decision is
stable.

What it does not settle is situation A's *quality*. Safe there mostly means `needs_approval` — the
suggestion defers instead of asking which environment the deployment targets. Only one call in
twelve reached `unclear`, which is the answer the case was written for.

## Why only nine of fifteen cases are identical

The variation is mostly refuse-or-answer rather than a different decision. Four calls were refused by
`suggest()`'s own cross-field check — the model classified a request as needing approval and set
`commits_to_something` anyway. A refusal shows the engineer no card, which is wrong, but it is not a
suggestion that gives something away. The summary counts refusals apart from safe answers for that
reason; counting them as passes would let a configuration that refused everything report as perfect.

## A stronger model is not currently a lever

`gemini-2.5-flash` failed all 45 calls: 38 `JSONDecodeError`, 7 `ClientError`. Whatever it returns is
not being parsed by the same response handling that works for flash-lite. That is a bug to
understand, not a result about the model, and until it is understood the model tier cannot be traded
against accuracy.

## What this changes about the other numbers

The turn-by-turn run in `20cases.md` produces a card per speaker turn, and its dangerous cards were
**intermediate** turns, not final decisions: case-05 confirmed an undefined deadline one turn before
it would have deferred, case-11 agreed to fix the reporting module on "It is a small thing" and
withdrew it on the next turn. This measurement only covers the final state, so it says nothing about
those. Both are real — the engineer reads whichever card is on screen — and they are a property of
showing a card per turn rather than of the decision contract.

Reproduce:

```powershell
op run --env-file .env.op -- python -m scripts.stability --repeats 3 --out docs/eval/run.csv
```

Raw: `docs/eval/stability.csv` (both models, current contract) and
`docs/eval/stability-authority.csv` (flash-lite, `82bdcb0`). Measurements only; the sentences go to a
gitignored `--review` dump.

## A defect only a counterpart that argues could find (2026-09-13)

`scripts/live_counterpart.py` runs a conversation through the real pipeline against a model playing
a client who pushes for a production date, with the engineer saying exactly what each card says. On
the shipped contract the card held the boundary for seven exchanges against three distinct pressure
tactics. It also exposed something none of the twenty cases contains:

In exchanges 5 and 6 the client stopped pushing and asked something else — *"When do you think you'll
be able to get back to me after checking internally?"* — which is the engineer's to answer. The card
kept classifying the old production request as the one on the table and repeated the deferral. On a
real call that makes the engineer sound like a recording.

Three attempts to fix it in `asked_for`, each measured with the fifteen A/C/D cases times three:

| Contract | Answered | Safe of answered | A answered `mine` | C answered `mine` | D `mine` |
|---|---|---|---|---|---|
| shipped (`4e5cc10`) | 41/45 | **39/41** | 1 of 12 | **0** | **15/15** |
| judge the latest utterance | 45/45 | 38/45 | 3 of 15 | 1 | 12/15 |
| pressure keeps a request, a new one replaces it | 40/45 | 33/40 | 4 of 14 | 1 | 13/15 |

Both were worse on the claim the product rests on, and both put a production agreement into
situation C, so both were reverted. The mechanism for the first is visible in the cases: a pressure
line — *"You are the engineer on it, so your word is enough"* — does not restate the request it is
pushing on, so a contract that looks only at the latest line loses the request and judges the
pressure. The defect stays open. The live counterpart is now the way to test a fix, because the
twenty cases cannot see it.

A likely explanation for `gemini-2.5-flash` failing all 45 calls above, not yet verified:
`GeminiJsonModel` caps output at 600 tokens, and a thinking model spends output tokens on thinking
before it writes, so the JSON would be cut off mid-object. The counterpart in `live_counterpart.py`
runs the same model with a thinking budget of zero and returns complete lines.
