"""Stand-in remote participant for the G1 test when nobody else is available.

Launches a separate Chromium (Playwright's build, fresh profile) whose microphone is a WAV file, so it can join a
Google Meet as an anonymous guest and "speak" the sample conversation. The host (you, in your normal browser)
admits it, then captures the Meet tab from the app.

  python scripts/meet_guest.py --selftest                 # prove the fake mic carries audio (prints RMS)
  python scripts/meet_guest.py https://meet.google.com/xxx-yyyy-zzz

Nothing here logs in anywhere; the guest joins by name only.
"""
from __future__ import annotations

import argparse
import asyncio
import glob
import json
import os
import subprocess
import sys
import tempfile
import urllib.request

WAV = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "samples", "meet-guest.wav"))
PORT = 9333

SELFTEST_HTML = """<html><body><script>
navigator.mediaDevices.getUserMedia({audio:true}).then(s=>{const c=new AudioContext();const src=c.createMediaStreamSource(s);
const an=c.createAnalyser();an.fftSize=2048;src.connect(an);const buf=new Float32Array(an.fftSize);window.peak=0;
setInterval(()=>{an.getFloatTimeDomainData(buf);let r=0;for(const v of buf)r+=v*v;r=Math.sqrt(r/buf.length);window.rms=r;window.peak=Math.max(window.peak,r);},100);
}).catch(e=>{window.err=String(e)});
</script></body></html>"""


def build_wav() -> None:
    """5 s lead-in, samples 01..03 with 4 s gaps, 48 kHz mono 16-bit (what Chromium's fake mic expects)."""
    import array
    import wave

    out = wave.open(WAV, "wb"); out.setnchannels(1); out.setsampwidth(2); out.setframerate(48000)
    sil = lambda s: bytes(2 * int(48000 * s))
    out.writeframes(sil(5))
    for src in sorted(glob.glob(os.path.join(os.path.dirname(WAV), "sample-0*.wav"))):
        w = wave.open(src, "rb")
        assert (w.getnchannels(), w.getsampwidth()) == (1, 2), src
        pcm = array.array("h", w.readframes(w.getnframes()))
        k = 48000 // w.getframerate()  # ponytail: samples are 16 kHz, so plain 3x repeat; audioop is gone in 3.13
        out.writeframes(array.array("h", (v for v in pcm for _ in range(k))).tobytes()); out.writeframes(sil(4))
    out.close()


def chrome() -> str:
    c = sorted(glob.glob(os.path.expanduser("~/AppData/Local/ms-playwright/chromium-*/chrome-win64/chrome.exe")))
    if not c:
        sys.exit("no Playwright Chromium found under ~/AppData/Local/ms-playwright")
    return c[-1]


def launch(url: str, profile: str, loop: bool) -> subprocess.Popen:
    wav = WAV + ("" if loop else "%noloop")
    return subprocess.Popen([
        chrome(), f"--user-data-dir={profile}", "--no-first-run", "--no-default-browser-check",
        "--use-fake-device-for-media-stream", f"--use-file-for-fake-audio-capture={wav}",
        "--use-fake-ui-for-media-stream",  # auto-grant mic/cam so the guest can join without a prompt
        f"--remote-debugging-port={PORT}", "--window-size=1100,800", url,
    ])


async def selftest(proc: subprocess.Popen) -> int:
    import websockets  # dev dependency

    await asyncio.sleep(3)
    tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json"))
    ws_url = next(t["webSocketDebuggerUrl"] for t in tabs if t["type"] == "page")
    async with websockets.connect(ws_url, max_size=None) as ws:
        async def ev(expr: str):
            await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True}}))
            while True:
                m = json.loads(await ws.recv())
                if m.get("id") == 1:
                    return m["result"]["result"].get("value")
        await asyncio.sleep(12)  # 5 s lead-in silence + first sentence
        err, peak = await ev("window.err"), await ev("window.peak")
        print(f"fake mic: err={err} peak_rms={peak}")
        return 0 if err is None and peak and peak > 0.01 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url", nargs="?")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--loop", action="store_true", help="repeat the WAV forever (default: play once)")
    a = ap.parse_args()
    if not os.path.exists(WAV):
        build_wav()
    profile = tempfile.mkdtemp(prefix="meet-guest-")
    if a.selftest:
        page = os.path.join(profile, "selftest.html")
        open(page, "w").write(SELFTEST_HTML)
        proc = launch("file:///" + page.replace("\\", "/"), profile, loop=True)
        try:
            return asyncio.run(selftest(proc))
        finally:
            proc.terminate()
    if not a.url:
        ap.error("meet url required")
    proc = launch(a.url, profile, loop=a.loop)
    print("guest browser open. In that window: type a name, click 'Ask to join'. In the host: admit it.")
    print("audio starts 5 s after the mic opens and runs ~113 s. Close the window to end.")
    proc.wait()
    return 0


if __name__ == "__main__":
    sys.exit(main())
