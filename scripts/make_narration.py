"""Render the submission video's narration with Google Cloud Text-to-Speech, one file per cue.

The narration is kept here rather than in docs/submission/demo-script.md so the words that get
spoken and the words that get reviewed cannot drift apart; the script prints them with --list.

One file per cue rather than one long track: the demo cues have to land against what is happening
on screen, and separate files let the edit move them without re-rendering anything.

The voice is deliberately male. The remote participant in the demo is Windows SAPI's Zira, and a
narrator sharing that voice would leave a viewer unsure who is speaking.

  python scripts/make_narration.py --list          # print the script and its timing, render nothing
  python scripts/make_narration.py                 # render to samples/narration/
"""
from __future__ import annotations

import argparse
import base64
import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "samples" / "narration"
PROJECT = "meeting-shadow-toki-260907"
VOICE = "en-US-Chirp3-HD-Charon"
API = "https://texttospeech.googleapis.com/v1/text:synthesize"

# (cue id, where it lands in the cut, what is said). Spoken length is roughly words / 2.5 seconds.
CUES: list[tuple[str, str, str]] = [
    ("01-problem", "0:00",
     "An engineer on an English delivery call understands every word, and still says yes before the "
     "conditions are settled. Which environment. Whose approval. By when. The cost arrives weeks later."),
    ("02-demo-open", "0:13",
     "This is a live call. The engineer's memo says staging validation is theirs to agree. Production is not."),
    ("03-demo-card1", "0:27",
     "The other side asks about a production rollout. The card marks that as still open."),
    ("04-demo-card2", "0:39",
     "Then they correct themselves, and production leaves the card. Only the staging scope is still open."),
    ("05-how", "0:47",
     "Tab audio goes straight from the browser to AssemblyAI Universal 3.5 Pro Realtime over a WebSocket. "
     "The server never holds the stream. Each finished turn goes to Gemini 2.5 Flash Lite, which has to cite "
     "the utterance it used. A suggestion citing something nobody said is refused, not repaired. The agent "
     "never speaks, never joins the call, and never sends anything on the engineer's behalf."),
    ("06-measured", "1:12",
     "Twenty scripted scenarios: twelve synthetic, eight read by a person. Conditions left undefined, "
     "conditions the speaker revises, requests that conflict with the memo, and conversations already "
     "settled. Median one point nine seconds from the end of speech to the card. Zero dangerous commitments "
     "across every run. This is a developer-authored test suite, not a field study. Zero failures in twenty "
     "trials still leaves a one-sided ninety-five percent upper bound near fourteen percent."),
    ("07-closing", "1:42",
     "For non-native engineers on English delivery calls. The live demo needs a Google sign-in. "
     "The recorded replay needs nothing."),
]


def token() -> str:
    # gcloud is a .cmd on Windows, which CreateProcess will not find without the extension.
    exe = shutil.which("gcloud")
    if not exe:
        sys.exit("gcloud is not on PATH")
    r = subprocess.run([exe, "auth", "print-access-token"], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"gcloud auth failed: {r.stderr.strip()[:200]}")
    return r.stdout.strip()


def synthesize(text: str, access: str) -> bytes:
    body = json.dumps({
        "input": {"text": text},
        "voice": {"languageCode": "en-US", "name": VOICE},
        "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 24000},
    }).encode()
    req = urllib.request.Request(API, data=body, headers={
        "Authorization": f"Bearer {access}", "x-goog-user-project": PROJECT,
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req) as r:
            return base64.b64decode(json.loads(r.read())["audioContent"])
    except urllib.error.HTTPError as e:
        sys.exit(f"synthesis failed ({e.code}): {e.read().decode()[:300]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="print the narration and its timing, render nothing")
    a = ap.parse_args()

    if a.list:
        total = 0
        for cue, at, text in CUES:
            words = len(text.split())
            total += words
            print(f"{at:>5}  {cue:16} {words:3} words  ~{words / 2.5:4.1f}s")
            print(f"       {text}\n")
        print(f"       {total} words, ~{total / 2.5:.0f}s of speech in a 120 s cut")
        return 0

    OUT.mkdir(parents=True, exist_ok=True)
    access = token()
    for cue, at, text in CUES:
        path = OUT / f"{cue}.wav"
        path.write_bytes(synthesize(text, access))
        secs = path.stat().st_size / (24000 * 2)
        print(f"{at:>5}  {path.name:22} {secs:4.1f}s")
    print(f"\n{VOICE} -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
