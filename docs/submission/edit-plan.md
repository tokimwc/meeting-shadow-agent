# The 120-second cut

Runs 1:50, not 2:00. The two minutes lablab allows is a ceiling; ten seconds of filler costs more
than it buys.

Three sources: `samples/narration/*.wav` (Google Cloud TTS, `en-US-Chirp3-HD-Charon`), the masked
demo clip, and whatever stills the title and closing cards need.

| At | Track | Source | Length |
|---|---|---|---|
| 0:00 | narration | `01-problem.wav` | 12.8 s |
| 0:13 | narration | `02-demo-open.wav` | 6.6 s |
| 0:20 | **demo footage starts** | `demo-final.mp4`, its own audio kept | 26 s |
| 0:25 | *(in footage)* first turn ends | | |
| 0:27 | *(in footage)* first card appears, 1,357 ms after the turn | | |
| 0:27 | narration | `03-demo-card1.wav` | 5.0 s |
| 0:38 | *(in footage)* correction ends | | |
| 0:39 | *(in footage)* second card appears, 1,234 ms after the turn | | |
| 0:39 | narration | `04-demo-card2.wav` | 6.1 s |
| 0:46 | demo footage ends | | |
| 0:47 | narration | `05-how.wav` | 24.6 s |
| 1:12 | narration | `06-measured.wav` | 29.8 s |
| 1:42 | narration | `07-closing.wav` | 7.9 s |
| 1:50 | end | | |

The two narration cues inside the demo sit in gaps where nobody is speaking: 0:27–0:33 falls between
the first card and the correction, and 0:39 onward falls after the second card. Neither talks over
the synthetic voice, so the demo audio stays audible and unedited.

Under the narration from 0:47 the demo can keep playing muted, or the slides can carry it — the
architecture diagram under `05-how`, the run table under `06-measured`. What must not happen is a
cut back to a card the recording never produced.

Say once, on screen or in the description: **the remote participant is a synthetic voice.** The
product's behaviour is real; a viewer should not have to guess whether a second person was there.

## Already masked in `demo-final.mp4`

The sharing bar across the top is filled black, and both participant name labels are blurred. The
meeting code and the avatar initial are left as they are, deliberately.
