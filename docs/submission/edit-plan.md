# The submission video

`samples/video/submission.mp4`, 109.9 s, 1920x1080, built by one command and not edited by hand:

```bash
op run --env-file .env.op -- python -m scripts.live_counterpart diego --out samples/live/diego
python scripts/make_narration.py
python scripts/make_video.py --conversation samples/live/diego --exchanges 2
```

The first line is the only one that calls AssemblyAI and Gemini, and its output is kept, so the video
can be rebuilt from the same conversation without paying for it again or getting a different one.

| At | Screen | Sound |
|---|---|---|
| 0:00 | deck slide 1, the problem | `01-problem` |
| 0:13 | the app, memo filled in, no card yet | `02-demo-open` — both voices are synthetic, the engineer says only what the card says |
| 0:23 | **the call**: exchanges 1 and 2 with Diego | the call only, no narration over it |
| 1:06 | deck slide 3, how it is built | `03-how` |
| 1:24 | deck slide 4, the memo flips the decision | `04-measured` |
| 1:40 | closing card with the replay and repository URLs | `05-closing` |

## What is on screen during the call, and what is not

Every frame is the app's own `index.html` and `app.js`, driven through `onMessage` and
`renderSuggestion` with what the recorded run returned — the transcript from AssemblyAI, the card
from `suggest()`. A strip along the bottom says it is a re-rendered recorded run, so it cannot pass
for a screen recording. The debug log panel is hidden because its timestamps would be render time.

Two simplifications, both named in `make_video.py`: a line that closed as several turns shows them
at once with its last card only (the one intermediate card skipped in this cut was "nothing asked
yet" on a greeting), and the partial transcript that streams while someone speaks is not drawn.

The card's latency label is the suggestion call alone (1,339 ms and 1,840 ms), which is what the
app's own label measures from turn arrival; it has no HTTP round trip in it.

## Why exchanges 1 and 2

Exchange 1 is the request and the deferral. Exchange 2 is the client saying the engineer's word is
enough, and the card deferring anyway — the one move a general-purpose assistant that wants to be
helpful is worst at. Exchanges 3 and 4 repeat that under different pressure and would push the cut
past two minutes. Exchanges 5 and 6 are where the card fails to notice the client changed the
question, recorded in `docs/eval/stability.md`; they are not in the video, and the description says
the defect exists.

## Cover image

`docs/submission/cover.html`, rendered headless at 2x into `docs/submission/assets/cover-3200x1800.png`.
The card on it is exchange 1's card word for word, so the cover, deck slide 2 and the video show the
same output.
