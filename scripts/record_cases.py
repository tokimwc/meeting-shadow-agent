"""Record the human half of samples/cases.json, one case at a time, straight to 16 kHz mono WAV.

Shows the lines to read, records until you press Enter, then plays it back so you can keep or redo it.

  python scripts/record_cases.py                  # record whatever is still missing
  python scripts/record_cases.py case-06          # redo one case
  python scripts/record_cases.py --device "..."   # pick a different microphone
  python scripts/record_cases.py --list-devices
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "samples" / "cases.json"
OUT = ROOT / "samples" / "cases"
# The ASCII alternative name: a Japanese device name does not survive the trip through ffmpeg on Windows.
DEFAULT_DEVICE = r"@device_cm_{33D9A762-90C8-11D0-BD43-00A0C911CE86}\wave_{A5178824-9E93-45BE-A282-A161859028F7}"

SITUATION = {
    "B": "the speaker corrects themselves partway through",
    "D": "everything here is already settled",
}


def devices() -> None:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    show = False
    for line in r.stderr.splitlines():
        text = line.split("] ", 1)[-1]
        if "(audio)" in text:
            print(text)
            show = True
        elif show and "Alternative name" in text:
            print(f"    {text.strip()}")
            show = False


def record(device: str, dst: Path) -> None:
    """ffmpeg records until it reads 'q' on stdin, which is what Enter gives us."""
    p = subprocess.Popen(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "dshow", "-i", f"audio={device}",
         "-ac", "1", "-ar", "16000", "-acodec", "pcm_s16le", str(dst)],
        stdin=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    input()
    p.communicate("q\n", timeout=30)
    if p.returncode not in (0, 255) and not dst.exists():
        sys.exit(f"ffmpeg failed ({p.returncode}). Check the device name with --list-devices.")


def peak(path: Path) -> tuple[float, float]:
    """Seconds and peak amplitude 0..1, so a silent take is obvious without listening."""
    import struct
    with wave.open(str(path), "rb") as w:
        n = w.getnframes()
        pcm = w.readframes(n)
    if not pcm:
        return 0.0, 0.0
    vals = struct.unpack(f"<{len(pcm) // 2}h", pcm)
    return n / 16000, max(abs(v) for v in vals) / 32768


def play(path: Path) -> None:
    subprocess.run(["ffplay", "-hide_banner", "-loglevel", "error", "-nodisp", "-autoexit", str(path)],
                   capture_output=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*", help="case ids to record (default: every human case still missing)")
    ap.add_argument("--device", default=DEFAULT_DEVICE)
    ap.add_argument("--list-devices", action="store_true")
    a = ap.parse_args()

    if a.list_devices:
        devices()
        return 0

    cases = json.loads(CASES.read_text(encoding="utf-8"))["cases"]
    human = [c for c in cases if c["audio"] == "human"]
    if a.ids:
        todo = [c for c in human if c["id"] in a.ids]
        missing = set(a.ids) - {c["id"] for c in todo}
        if missing:
            sys.exit(f"not human cases: {', '.join(sorted(missing))}")
    else:
        todo = [c for c in human if not (OUT / f"{c['id']}.wav").exists()]

    if not todo:
        print("Every human case already has a recording. To redo them, name the ids:")
        print(f"  python scripts/record_cases.py {' '.join(c['id'] for c in human)}")
        return 0

    OUT.mkdir(parents=True, exist_ok=True)
    print(f"Recording {len(todo)} case(s) from: {a.device}")
    print("You are the OTHER person on the call. Leave about a second of silence between the two lines.\n")

    for c in todo:
        dst = OUT / f"{c['id']}.wav"
        while True:
            print(f"--- {c['id']}  ({c['axis']}, {SITUATION[c['situation']]})")
            for line in c["lines"]:
                print(f'      "{line}"')
            input("\n    Enter to start recording... ")
            print("    RECORDING - read the lines, then press Enter to stop.")
            record(a.device, dst)
            secs, amp = peak(dst)
            print(f"    {secs:.1f}s, peak {amp:.2f}", end="")
            if amp < 0.02:
                print("  <-- almost silent, check the microphone")
            elif amp > 0.98:
                print("  <-- clipping, move back or lower the gain")
            else:
                print()
            play(dst)
            again = input("    [Enter] keep, [r] redo, [q] stop here: ").strip().lower()
            if again == "q":
                return 0
            if again != "r":
                break
        print()

    print("Done. Check the full set with: python scripts/make_cases.py --list")
    return 0


if __name__ == "__main__":
    sys.exit(main())
