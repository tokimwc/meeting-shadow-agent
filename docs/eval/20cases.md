# 20-case evaluation (2026-09-11)

Twenty audio cases in `samples/cases.json`: five axes (environment, deadline, scope, authority,
effort) crossed with four situations. Twelve are Windows SAPI, eight are read by a person. Only the
remote participant speaks; the engineer never does.

| Situation | The suggestion must |
|---|---|
| A | ask for the one thing the utterances left undefined |
| B | apply the speaker's own correction |
| C | decline what the memo places outside the engineer's authority |
| D | ask nothing — everything is already settled |

Latency and safety are machine-checked by `scripts/e2e_eval.py`; whether the suggestion is *right*
is judged by hand against each case's `expect_clarify` / `expect_not`. The CSVs carry measurements
only — the suggestion text goes to a gitignored `--review` dump, which is what the hand pass reads.

## Runs

| Run | Commit | A | B | C | D | Total | median | p90 | commits |
|---|---|---|---|---|---|---|---|---|---|
| baseline | `fdc6711` | 0/5 | 5/5 | 4/5 | 1/4 | 10/20 | 2.05 s | 2.52 s | 0 |
| grounded | `0aa6d29` | 2/5 | 4/5 | 3/5 | 2/4 | 11/20 | 1.89 s | 2.36 s | 0 |
| undefined | `edfad15` | 4/5 | 4/5 | 3/5 | 2/4 | **13/20** | 1.90 s | 2.39 s | 0 |
| no examples | `c0c541e` | 1/5 | 4/5 | 2/5 | 2/4 | 9/20 | 1.89 s | 2.39 s | 0 |

Shipping `edfad15`, restored in `b2235cb` after the fourth run scored worse.

Safety held in every run: zero dangerous commitments and zero invalid evidence ids across all turns.
What the cases measured is usefulness.

## What the baseline got wrong

Situations A and D failed the same way. Asked which environment a deployment targeted, the model
answered with the memo's list of things needing approval. It named a production deployment in eight
cases where nobody had mentioned production, and manufactured open items in cases where the speaker
had just settled everything.

The system prompt already said the memo is not evidence that others requested production, so the
grounding moved into the contract instead: an unconfirmed item has to cite the utterance that raised
it, `m0` alone is the memo talking, and `suggest()` drops those items rather than trusting the
instruction. The prompt also stopped reciting the five axes, which read as a checklist to fill in.

That removed the invented production deployments entirely. Two situation-B and C cases scored lower
afterwards, both for reasons worth keeping: case-10 had stopped inventing a clean reading of a
garbled transcript, and cases 11 and 19 now ask about scope without naming the approval boundary.

With the memo out of the way, situation A exposed a second defect: the model asks about whichever
detail is most salient rather than the one that is missing. Told "we need the fix deployed by the
end of this week", it asked to confirm the deadline — the one thing the speaker had given — and left
the environment unasked. Telling it to ask about what the utterances left undefined, with three
examples, took situation A from 2/5 to 4/5.

## The examples cut both ways

One of those three examples was a timezone, and the next run asked about a timezone in four cases,
two of them cases that were supposed to ask nothing at all. That is the same failure as the five
axes the prompt used to recite, one level down: a concrete example reads as a default rather than an
illustration. Removing the examples stopped the tic and cost situation A three cases, back to 1/5 —
the principle does not survive on its own. The examples are back, and the tic is the price.

## What is left

Two failures survive every configuration tried, and they pull against each other. Situation A needs
the suggestion to always find something to ask; situation D needs it to recognise when to ask
nothing, and both are steered from the same paragraph. The `unconfirmed` list is empty in three of
the four D cases, which is correct, and the suggestion still asks a question anyway. Cases 11 and 19
ask about scope without naming the approval boundary the memo draws.

Neither looks like a wording problem, so they are recorded rather than chased.

## Known limitation: non-native speech

The eight human recordings are read by a non-native English speaker. `staging`, `production` and the
weekday names survive, but case-10 loses "Oh, and the ... goes with it" to "Oh. End of day. ...
Cause visit.", and the suggestion degrades with it. A first take also turned `Legal` into `Diego`
when it opened a sentence alone; the line is now "The legal team has already approved this."

This is a real property of the product, not an artifact of the test set: the decision-bearing words
are exactly the ones a strong accent puts at risk. It belongs in the submission as a limitation, not
hidden by replacing the human takes with synthesis.
