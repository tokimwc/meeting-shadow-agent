"""Assemble the 20 evaluation cases in samples/cases.json as 16 kHz mono WAV.

Synthetic cases are rendered with Windows SAPI. Human cases are recorded by a person in whatever
format is convenient and converted here with ffmpeg.

  python scripts/make_cases.py            # render missing synthetic files
  python scripts/make_cases.py --force    # re-render everything
  python scripts/make_cases.py --list     # print the plan, touch nothing
  python scripts/make_cases.py --script   # print the recording script for the human cases
  python scripts/make_cases.py --import   # convert samples/recordings/case-NN.* into place
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import wave
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "samples" / "cases.json"
OUT = ROOT / "samples" / "cases"
VOICE = "Microsoft Zira Desktop"  # a synthetic voice, not a real person
GAP_MS = 900  # long enough for AssemblyAI to end the turn between lines

PS = """
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, `
  [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, `
  [System.Speech.AudioFormat.AudioChannel]::Mono)
try { $s.SelectVoice('%(voice)s') } catch { Write-Host "voice '%(voice)s' unavailable, using default" }
$s.SetOutputToWaveFile('%(path)s', $fmt)
$s.SpeakSsml(@'
%(ssml)s
'@)
$s.SetOutputToNull()
$s.Dispose()
"""


def ssml(lines: list[str]) -> str:
    body = f'<break time="{GAP_MS}ms"/>'.join(escape(x) for x in lines)
    # A trailing pause so the last turn ends inside the recording rather than at EOF.
    return ('<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">'
            f'{body}<break time="{GAP_MS}ms"/></speak>')


def render(case: dict, path: Path) -> None:
    script = PS % {"voice": VOICE, "path": str(path), "ssml": ssml(case["lines"])}
    r = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"{case['id']}: SAPI failed\n{r.stderr.strip()}")
    if r.stdout.strip():
        print(f"  {r.stdout.strip()}")


def check(path: Path) -> str:
    with wave.open(str(path), "rb") as w:
        got = (w.getnchannels(), w.getsampwidth(), w.getframerate())
        if got != (1, 2, 16000):
            sys.exit(f"{path.name}: expected mono/16-bit/16 kHz, got {got}")
        return f"{w.getnframes() / 16000:.1f}s"


def convert(src: Path, dst: Path) -> None:
    r = subprocess.run(["ffmpeg", "-y", "-i", str(src), "-ac", "1", "-ar", "16000",
                        "-acodec", "pcm_s16le", str(dst)], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"{src.name}: ffmpeg failed\n{r.stderr.strip()[-500:]}")


def recording_script(human: list[dict]) -> None:
    print("Record these as the remote participant. You are the other side of the call, not yourself.\n")
    print("  - Leave about a second of silence between the two lines: that gap is what ends the turn.")
    print("  - Normal speaking pace. Do not perform an accent; a natural read is what is being tested.")
    print("  - Any format ffmpeg reads (m4a from a phone is fine). Name the file after the case id.")
    print(f"  - Drop them in samples{chr(92)}recordings{chr(92)}, then run: python scripts/make_cases.py --import\n")
    for c in human:
        print(f"{c['id']}  ({c['axis']}, {'correction mid-conversation' if c['situation'] == 'B' else 'already settled'})")
        for line in c["lines"]:
            print(f'    "{line}"')
        print()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-render files that already exist")
    ap.add_argument("--list", action="store_true", help="print the plan and exit")
    ap.add_argument("--script", action="store_true", help="print the recording script for the human cases")
    ap.add_argument("--import", dest="do_import", action="store_true",
                    help="convert samples/recordings/case-NN.* to 16 kHz mono WAV in samples/cases/")
    a = ap.parse_args()

    cases = json.loads(CASES.read_text(encoding="utf-8"))["cases"]
    synthetic = [c for c in cases if c["audio"] == "synthetic"]
    human = [c for c in cases if c["audio"] == "human"]

    if a.script:
        recording_script(human)
        return 0

    if a.list:
        for c in cases:
            path = OUT / f"{c['id']}.wav"
            state = check(path) if path.exists() else "MISSING"
            print(f"{c['id']}  {c['axis']:11} {c['situation']}  {c['audio']:9} {state}")
        missing = [c["id"] for c in cases if not (OUT / f"{c['id']}.wav").exists()]
        print(f"\n{len(cases) - len(missing)}/{len(cases)} ready" +
              (f", missing: {', '.join(missing)}" if missing else ""))
        return 0

    if a.do_import:
        src_dir = ROOT / "samples" / "recordings"
        if not src_dir.exists():
            sys.exit(f"no {src_dir}. Record the human cases first: python scripts/make_cases.py --script")
        OUT.mkdir(parents=True, exist_ok=True)
        for c in human:
            found = [p for p in src_dir.glob(f"{c['id']}.*") if p.suffix.lower() != ".wav" or p.parent != OUT]
            if not found:
                print(f"{c['id']}  no recording found in {src_dir.name}/")
                continue
            dst = OUT / f"{c['id']}.wav"
            convert(found[0], dst)
            print(f"{c['id']}  {found[0].name} -> {dst.name}  {check(dst)}")
        return 0

    OUT.mkdir(parents=True, exist_ok=True)
    for c in synthetic:
        path = OUT / f"{c['id']}.wav"
        if path.exists() and not a.force:
            print(f"{c['id']}  skip (exists, {check(path)})")
            continue
        render(c, path)
        print(f"{c['id']}  {check(path)}")

    print(f"\nRecord these {len(human)} by hand into {OUT}, same format "
          f"(16 kHz mono PCM16), one file per case:")
    for c in human:
        print(f"  {c['id']}.wav  {c['axis']} {c['situation']}")
        for line in c["lines"]:
            print(f"      \"{line}\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
