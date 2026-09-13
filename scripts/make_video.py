"""Assemble the submission video from the recorded conversation, the narration and the deck.

Every frame of the call is the app's own index.html and app.js, fed the recorded run through the same
functions a live session calls (`onMessage` for a finalised turn, `renderSuggestion` for a card), then
photographed. Nothing on screen is typed in by hand: the transcript is what AssemblyAI returned and
the card is what `suggest()` returned. A strip along the bottom says so, because a re-rendered screen
that did not would be passing itself off as a screen recording.

  python scripts/make_video.py --conversation samples/live/diego --exchanges 2 --out samples/video/submission.mp4

Needs ffmpeg on PATH and the Playwright Chromium the other scripts use.
"""
from __future__ import annotations

import argparse
import glob
import html
import json
import os
import shutil
import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "app" / "static"
NARRATION = ROOT / "samples" / "narration"
DECK = ROOT / "docs" / "submission" / "slides.html"
W, H = 1920, 1080
RATE = 48000
REPLAY_URL = "tokimwc.github.io/meeting-shadow-agent/replay"
REPO_URL = "github.com/tokimwc/meeting-shadow-agent"

# Pacing of the call. The card's arrival is measured; these are only the pauses around speech.
LEAD, BEAT, GAP, TAIL = 0.6, 1.0, 0.6, 1.0


def chrome() -> str:
    found = sorted(glob.glob(os.path.expanduser("~/AppData/Local/ms-playwright/chromium-*/chrome-win64/chrome.exe")))
    if not found:
        sys.exit("no Playwright Chromium under ~/AppData/Local/ms-playwright")
    return found[-1]


def shoot(page: Path, png: Path, width: int = 1440, height: int = 810) -> None:
    # Rendered at 1440x810 and scaled 4/3, so text is laid out at a readable size and lands on 1080p crisp.
    subprocess.run([chrome(), "--headless", "--disable-gpu", "--hide-scrollbars", f"--window-size={width},{height}",
                    f"--force-device-scale-factor={W / width}", "--virtual-time-budget=3000",
                    f"--screenshot={png}", page.as_uri()], check=True, capture_output=True)


def seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


def run(*args: str) -> None:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"ffmpeg failed: {r.stderr[-600:]}")


# ---- the call ------------------------------------------------------------------------------------

def call_page(frames: list[dict], out: Path) -> Path:
    """One page that renders any frame of the call from its URL hash, using the product's own client."""
    index = (STATIC / "index.html").read_text(encoding="utf-8")
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    stub = """<script>
  // A live session would call the service here. This page only draws what a recorded one returned.
  window.fetch = () => new Promise(() => {});
</script>"""
    driver = f"""<script>
const FRAMES = {json.dumps(frames, ensure_ascii=False)};
const n = Number(location.hash.slice(1) || 0);
document.getElementById("status").textContent = "音声を受信中";
for (const f of FRAMES.slice(0, n + 1)) {{
  for (const text of f.heard || []) onMessage({{ type: "Turn", end_of_turn: true, transcript: text }});
  if (f.card) renderSuggestion(f.card, f.ms);
}}
document.getElementById("status").textContent = "音声を受信中";
const who = FRAMES[n].speaker;
document.getElementById("speaker").textContent = who || "";
document.getElementById("speaker").hidden = !who;
</script>"""
    chrome_css = """<style>
  #log, section[style*="grid-column"] { display: none; }   /* timestamps there are render time, not call time */
  #speaker { position: fixed; left: 16px; bottom: 44px; padding: 6px 12px; border-radius: 3px;
    background: #1f2a33; color: #e6edf3; font: 600 13px system-ui, sans-serif; letter-spacing: .02em; }
  #strip { position: fixed; left: 0; right: 0; bottom: 0; padding: 7px 16px; background: #0b0f12;
    color: #8b98a5; font: 12px ui-monospace, Consolas, monospace; border-top: 1px solid #30363d; }
</style>"""
    overlay = ("<div id='speaker' hidden></div><div id='strip'>Recorded run through the live pipeline "
               "(AssemblyAI Universal-3.5 Pro Realtime → Gemini) · re-rendered in the app's own UI · "
               "both voices synthetic</div>")
    # The overlay has to exist before the driver runs, or the driver throws on it after drawing the card
    # and the speaker label silently never appears.
    page = (index.replace("</head>", chrome_css + "\n</head>")
                 .replace('<script src="/static/app.js"></script>',
                          overlay + "\n" + stub + "\n<script>" + app + "</script>\n" + driver))
    assert "<script>" + app in page, "index.html no longer loads app.js the way this expects"
    out.write_text(page, encoding="utf-8")
    return out


def build_call(conv: Path, exchanges: int, work: Path) -> tuple[list[tuple[Path, float]], Path]:
    d = json.loads((conv / "conversation.json").read_text(encoding="utf-8"))
    counterpart = d["role"].capitalize()
    frames: list[dict] = [{"speaker": None}]
    durations: list[float] = [LEAD]
    audio: list[tuple[str, float]] = [("silence", LEAD)]

    for ex in d["exchanges"][:exchanges]:
        last = ex["turns"][-1]
        # ponytail: a line that closes as several turns shows them all at once, with the last card only.
        # The intermediate cards are skipped; in the recorded run the only one that differed was a
        # "nothing asked yet" on a greeting. Render them individually if a cut ever needs to show one.
        them = conv / f"{ex['n']:02d}-counterpart.wav"
        me = conv / f"{ex['n']:02d}-engineer.wav"
        stt = last["t_stt"] or 0.0
        card = None
        if "authority" in last:
            card = {"summary_ja": last["summary_ja"], "asked_for": last["asked_for"], "authority": last["authority"],
                    "unconfirmed": [{"item": u, "evidence_ids": []} for u in last["unconfirmed"]],
                    "next_line_en": last["next_line_en"], "next_line_ja": last["next_line_ja"],
                    "evidence_ids": last["evidence_ids"], "commits_to_something": last["commits"]}
        frames.append({"speaker": f"● {counterpart} (client) speaking"})
        durations.append(seconds(them) + stt)
        audio += [(str(them), seconds(them)), ("silence", stt)]

        frames.append({"heard": [t["heard"] for t in ex["turns"]], "speaker": None})
        durations.append(last["t_llm"])
        audio.append(("silence", last["t_llm"]))

        frames.append({"card": card, "ms": round(last["t_llm"] * 1000), "speaker": None})
        durations.append(BEAT)
        audio.append(("silence", BEAT))

        frames.append({"speaker": "● Engineer saying the card" if ex["engineer_from_card"] else "● Engineer (no card)"})
        durations.append(seconds(me) + GAP)
        audio += [(str(me), seconds(me)), ("silence", GAP)]
    durations[-1] += TAIL
    audio.append(("silence", TAIL))

    page = call_page(frames, work / "call.html")
    shots = []
    for i, dur in enumerate(durations):
        png = work / f"call-{i:02d}.png"
        # Chrome's --screenshot ignores a fragment on a file URL, so each frame gets its own page.
        framed = work / f"call-{i:02d}.html"
        framed.write_text(page.read_text(encoding="utf-8").replace('location.hash.slice(1) || 0', str(i)), encoding="utf-8")
        shoot(framed, png)
        shots.append((png, dur))

    wav = work / "call.wav"
    parts = []
    for src, dur in audio:
        parts += (["-f", "lavfi", "-t", f"{dur:.3f}", "-i", f"anullsrc=r={RATE}:cl=stereo"] if src == "silence" else ["-i", src])
    n = len(audio)
    run(*parts, "-filter_complex",
        "".join(f"[{i}:a]aresample={RATE},aformat=channel_layouts=stereo[a{i}];" for i in range(n))
        + "".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[out]", "-map", "[out]", str(wav))
    return shots, wav


# ---- stills --------------------------------------------------------------------------------------

def slide(n: int, work: Path) -> Path:
    """One deck slide alone, dark, edge to edge."""
    src = DECK.read_text(encoding="utf-8")
    css = f"""<style>
  body {{ margin: 0 !important; }}
  .deck {{ padding: 0 !important; gap: 0 !important; max-width: none !important; }}
  .slide {{ border: 0 !important; }}
  .slide:not(:nth-of-type({n})) {{ display: none !important; }}
</style><script>document.documentElement.dataset.theme = "dark";</script>"""
    page = work / f"slide-{n}.html"
    # The deck has no <head> (it is written to be wrapped at publish time), so the override goes first;
    # !important lets it win without depending on where the deck's own rules land.
    page.write_text(css + "\n" + src, encoding="utf-8")
    png = work / f"slide-{n}.png"
    shoot(page, png, 1600, 900)
    return png


def closing(work: Path) -> Path:
    page = work / "closing.html"
    page.write_text(f"""<!doctype html><meta charset="utf-8">
<style>
  body {{ margin: 0; height: 100vh; display: grid; place-content: center; gap: 22px; background: #0F1519;
    color: #E6ECE8; font-family: "IBM Plex Sans", system-ui, sans-serif; text-align: center; }}
  h1 {{ font-family: "IBM Plex Serif", Georgia, serif; font-weight: 600; font-size: 54px; margin: 0; }}
  p {{ margin: 0; color: #9BAAB1; font-size: 22px; }}
  code {{ font-family: "IBM Plex Mono", Consolas, monospace; font-size: 24px; color: #52B7A4; }}
</style>
<h1>Meeting Shadow Agent</h1>
<p>Replay the recorded runs, no sign-in</p><code>{html.escape(REPLAY_URL)}</code>
<p style="margin-top:14px">Source and every evaluation run</p><code>{html.escape(REPO_URL)}</code>
""", encoding="utf-8")
    png = work / "closing.png"
    shoot(page, png, 1600, 900)
    return png


def still_with(png: Path, voice: Path | None, work: Path, name: str, pad: float = 0.6) -> Path:
    out = work / f"{name}.mp4"
    dur = (seconds(voice) if voice else 0) + pad
    audio = ["-i", str(voice)] if voice else ["-f", "lavfi", "-i", f"anullsrc=r={RATE}:cl=stereo"]
    run("-loop", "1", "-t", f"{dur:.3f}", "-i", str(png), *audio,
        "-filter_complex", f"[0:v]scale={W}:{H}:flags=lanczos,format=yuv420p,fps=30[v];"
                           f"[1:a]aresample={RATE},aformat=channel_layouts=stereo,apad[a]",
        "-map", "[v]", "-map", "[a]", "-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k", str(out))
    return out


def call_clip(shots: list[tuple[Path, float]], wav: Path, work: Path) -> Path:
    listing = work / "call.txt"
    lines = [f"file '{p.as_posix()}'\nduration {d:.3f}" for p, d in shots]
    listing.write_text("\n".join(lines) + f"\nfile '{shots[-1][0].as_posix()}'\n", encoding="utf-8")
    out = work / "call.mp4"
    run("-f", "concat", "-safe", "0", "-i", str(listing), "-i", str(wav),
        "-filter_complex", f"[0:v]scale={W}:{H}:flags=lanczos,format=yuv420p,fps=30[v]",
        "-map", "[v]", "-map", "1:a", "-shortest", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k", str(out))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--conversation", default="samples/live/diego")
    ap.add_argument("--exchanges", type=int, default=2)
    ap.add_argument("--out", default="samples/video/submission.mp4")
    a = ap.parse_args()
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg is not on PATH")

    out = ROOT / a.out
    work = out.parent / "work"
    work.mkdir(parents=True, exist_ok=True)

    shots, wav = build_call(ROOT / a.conversation, a.exchanges, work)
    # The app with the memo in place and no card yet, under the line that sets the call up.
    idle = work / "idle.png"
    shutil.copy(shots[0][0], idle)

    parts = [
        still_with(slide(1, work), NARRATION / "01-problem.wav", work, "p1"),
        still_with(idle, NARRATION / "02-demo-open.wav", work, "p2", pad=0.4),
        call_clip(shots, wav, work),
        still_with(slide(3, work), NARRATION / "03-how.wav", work, "p4"),
        still_with(slide(4, work), NARRATION / "04-measured.wav", work, "p5"),
        still_with(closing(work), NARRATION / "05-closing.wav", work, "p6", pad=1.2),
    ]
    listing = work / "parts.txt"
    listing.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    run("-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", "-movflags", "+faststart", str(out))

    total = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
                                 capture_output=True, text=True).stdout.strip())
    print(f"{out}  {total:.1f} s")
    return 0 if total <= 120 else 1


if __name__ == "__main__":
    sys.exit(main())
