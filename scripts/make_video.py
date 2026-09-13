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
# BEAT is a pause after the card lands so its verdict can be read; it is not part of any measured time.
LEAD, BEAT, GAP, TAIL = 0.6, 2.2, 0.6, 1.0


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
// The recorded figure is the suggestion call alone, not turn end → card on screen, so the label says so.
const shown = FRAMES.slice(0, n + 1).filter(f => f.card).pop();
if (shown) document.getElementById("latency").textContent = `suggestion call ${{shown.ms}} ms`;
// Where to look: a red box around the part of the screen this moment is about, with a label in English
// because the app's own headings are Japanese.
const FOCUS = {{
  listen: [["#turns", "#partial"], "① The client speaks — AssemblyAI transcribes it here, live"],
  verdict: [["#verdict"], "② The card: what is being asked, and whose decision it is"],
  reply: [["#nextEn", "#nextJa"], "③ The reply the engineer says, read straight from the card"],
}};
const focus = FOCUS[FRAMES[n].focus];
if (focus) {{
  const els = focus[0].map(s => document.querySelector(s));
  if (focus[0][0] === "#turns") els.push([...document.querySelectorAll("main h2")].find(h => h.textContent.includes("聞こえている英語")));
  if (focus[0][0] === "#verdict") els.push(els[0].previousElementSibling);
  if (focus[0][0] === "#nextEn") els.push(els[0].previousElementSibling);
  const rs = els.filter(Boolean).map(e => e.getBoundingClientRect());
  const top = Math.min(...rs.map(r => r.top)) - 10, left = Math.min(...rs.map(r => r.left)) - 12;
  const right = Math.max(...rs.map(r => r.right)) + 12;
  const bottom = Math.max(Math.max(...rs.map(r => r.bottom)) + 10, top + 90);
  const box = document.getElementById("focus");
  Object.assign(box.style, {{ top: top + "px", left: left + "px", width: (right - left) + "px", height: (bottom - top) + "px" }});
  box.querySelector("span").textContent = focus[1];
  box.hidden = false;
}}
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
  #focus { position: fixed; border: 4px solid #ff3b30; border-radius: 6px; box-shadow: 0 0 0 9999px rgba(0,0,0,.28);
    pointer-events: none; }
  #focus span { position: absolute; left: -4px; bottom: 100%; margin-bottom: 6px; white-space: nowrap;
    background: #ff3b30; color: #fff; font: 700 15px system-ui, sans-serif; padding: 5px 10px; border-radius: 4px; }
</style>"""
    overlay = ("<div id='focus' hidden><span></span></div><div id='speaker' hidden></div><div id='strip'>SIMULATED CALL · client played by Gemini 2.5 Flash · "
               "both voices TTS · audio through AssemblyAI realtime → suggest() · screen re-rendered from the run · "
               "exchanges 1–2 of 7</div>")
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
        frames.append({"focus": "listen", "speaker": f"● Simulated client “{counterpart}” — Gemini 2.5 Flash, TTS voice"})
        durations.append(seconds(them) + stt)
        audio += [(str(them), seconds(them)), ("silence", stt)]

        frames.append({"heard": [t["heard"] for t in ex["turns"]], "focus": "listen", "speaker": None})
        durations.append(last["t_llm"])
        audio.append(("silence", last["t_llm"]))

        frames.append({"card": card, "ms": round(last["t_llm"] * 1000), "focus": "verdict", "speaker": None})
        durations.append(BEAT)
        audio.append(("silence", BEAT))

        frames.append({"focus": "reply", "speaker": "● Engineer — TTS reading the card" if ex["engineer_from_card"] else "● Engineer (no card)"})
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
<p style="margin-top:14px">Source, eval notes, and the full simulated conversation</p><code>{html.escape(REPO_URL)}</code>
""", encoding="utf-8")
    png = work / "closing.png"
    shoot(page, png, 1600, 900)
    return png


def disclosure(work: Path) -> Path:
    """What the next minute is, on screen while the narration says it."""
    rows = [("The client", "Gemini 2.5 Flash, given a role and told to push back. Not a person."),
            ("The voices", "Both text-to-speech. The engineer's lines are each card's reply, read as is."),
            ("The pipeline", "Client audio streamed through AssemblyAI realtime into the same suggest() the service runs."),
            ("The screen", "The app's own UI re-rendered from that run. Not a screen recording."),
            ("The excerpt", "Exchanges 1–2 of 7. Later, the card keeps deferring after the client changes the question.")]
    page = work / "disclosure.html"
    page.write_text(f"""<!doctype html><meta charset="utf-8">
<style>
  body {{ margin: 0; height: 100vh; display: grid; place-content: center; background: #0F1519;
    color: #E6ECE8; font-family: "IBM Plex Sans", system-ui, sans-serif; }}
  h1 {{ font-family: "IBM Plex Serif", Georgia, serif; font-weight: 600; font-size: 50px; margin: 0 0 34px; }}
  dl {{ display: grid; grid-template-columns: 200px 1fr; gap: 18px 28px; margin: 0; max-width: 1200px; }}
  dt {{ font-family: "IBM Plex Mono", Consolas, monospace; font-size: 20px; color: #52B7A4; padding-top: 3px; }}
  dd {{ margin: 0; font-size: 27px; line-height: 1.35; }}
</style>
<h1>A simulated call</h1>
<dl>{"".join(f"<dt>{html.escape(k)}</dt><dd>{html.escape(v)}</dd>" for k, v in rows)}</dl>
""", encoding="utf-8")
    png = work / "disclosure.png"
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
    # -shortest does not reliably stop a filter_complex output: the concat demuxer's repeated last frame ran
    # the video 2.6 s past the audio, and every segment after it played its narration ~2 s ahead of its
    # slide. Cut to the audio's own length instead.
    run("-f", "concat", "-safe", "0", "-i", str(listing), "-i", str(wav),
        "-filter_complex", f"[0:v]scale={W}:{H}:flags=lanczos,format=yuv420p,fps=30[v]",
        "-map", "[v]", "-map", "1:a", "-t", f"{seconds(wav):.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
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
    parts = [
        still_with(slide(1, work), NARRATION / "01-problem.wav", work, "p1"),
        # What the call is goes on screen, not only in the narration, before any of it plays.
        still_with(disclosure(work), NARRATION / "02-demo-open.wav", work, "p2", pad=1.0),
        call_clip(shots, wav, work),
        still_with(slide(3, work), NARRATION / "03-how.wav", work, "p4"),
        still_with(slide(4, work), NARRATION / "04-measured.wav", work, "p5"),
        still_with(closing(work), NARRATION / "05-closing.wav", work, "p6", pad=1.2),
    ]
    listing = work / "parts.txt"
    listing.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    # Speech at -21 LUFS is too quiet on laptop speakers; -16 is the usual target for spoken web video.
    run("-f", "concat", "-safe", "0", "-i", str(listing), "-c:v", "copy",
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", str(RATE), "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", str(out))
    for part in parts:
        v, a = (float(subprocess.run(["ffprobe", "-v", "error", "-select_streams", s, "-show_entries", "stream=duration",
                                      "-of", "csv=p=0", str(part)], capture_output=True, text=True).stdout.strip())
                for s in ("v", "a"))
        # Any segment whose picture outlasts its sound shifts every later narration off its slide.
        assert abs(v - a) < 0.1, f"{part.name}: video {v:.2f}s against audio {a:.2f}s"

    total = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
                                 capture_output=True, text=True).stdout.strip())
    print(f"{out}  {total:.1f} s")
    return 0 if total <= 120 else 1


if __name__ == "__main__":
    sys.exit(main())
