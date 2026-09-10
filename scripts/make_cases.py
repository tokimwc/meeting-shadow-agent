"""Render the synthetic half of samples/cases.json to 16 kHz mono WAV using Windows SAPI.

The human-recorded cases are left to a person; this only touches `"audio": "synthetic"` entries.

  python scripts/make_cases.py            # render missing files
  python scripts/make_cases.py --force    # re-render everything
  python scripts/make_cases.py --list     # print what would be rendered, touch nothing
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-render files that already exist")
    ap.add_argument("--list", action="store_true", help="print the plan and exit")
    a = ap.parse_args()

    cases = json.loads(CASES.read_text(encoding="utf-8"))["cases"]
    synthetic = [c for c in cases if c["audio"] == "synthetic"]
    human = [c for c in cases if c["audio"] == "human"]

    if a.list:
        for c in synthetic:
            print(f"{c['id']}  {c['axis']:11} {c['situation']}  {len(c['lines'])} lines")
        print(f"\n{len(synthetic)} synthetic, {len(human)} to record by hand: "
              f"{', '.join(c['id'] for c in human)}")
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
