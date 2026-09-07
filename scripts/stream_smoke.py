"""Stream a 16 kHz mono PCM16 WAV to AssemblyAI realtime at real-time pace and measure turn latency.

Usage (key injected by op run, never stored):
  op run --env-file .env.op -- python scripts/stream_smoke.py samples/sample-01.wav [--mode balanced] [--out docs/eval/latency.csv]

Latency definition (G2 in docs/week1-plan.md): time from the last *non-silent* audio chunk of an utterance being sent
to the `Turn` message with end_of_turn=true arriving. Silence is detected client-side (RMS threshold) so the number
is comparable across runs. The suggestion (Gemini) leg is measured separately in the browser.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import struct
import sys
import time
import wave
from urllib.parse import urlencode

import websockets

WS = "wss://streaming.assemblyai.com/v3/ws"
CHUNK_MS = 100
SILENCE_RMS = 300  # int16 RMS; SAPI/room noise floor is far below this


def rms(pcm: bytes) -> float:
    n = len(pcm) // 2
    if n == 0:
        return 0.0
    vals = struct.unpack(f"<{n}h", pcm)
    return (sum(v * v for v in vals) / n) ** 0.5


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("wav")
    ap.add_argument("--mode", default="balanced", choices=["min_latency", "balanced", "max_accuracy"])
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    key = os.environ.get("ASSEMBLYAI_API_KEY", "")
    if not key:
        sys.exit("ASSEMBLYAI_API_KEY missing (run via op run)")

    w = wave.open(a.wav, "rb")
    assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, 16000), "need 16 kHz mono PCM16"
    frames_per_chunk = 16000 * CHUNK_MS // 1000

    q = urlencode({
        "speech_model": "universal-3-5-pro", "encoding": "pcm_s16le", "sample_rate": 16000,
        "mode": a.mode, "language_codes": "en",
        "prompt": "English technical meeting between software engineers about delivery dates, environments (staging vs production), scope and approvals.",
    })
    t0 = time.perf_counter()
    last_voice_t: float | None = None
    turns: list[dict] = []
    finals: list[dict] = []

    async with websockets.connect(f"{WS}?{q}", additional_headers={"Authorization": key}, max_size=None) as ws:
        async def send():
            nonlocal last_voice_t
            while True:
                pcm = w.readframes(frames_per_chunk)
                if not pcm:
                    break
                if rms(pcm) > SILENCE_RMS:
                    last_voice_t = time.perf_counter()
                await ws.send(pcm)
                await asyncio.sleep(CHUNK_MS / 1000)  # real-time pacing (server closes 3007 if faster)
            await asyncio.sleep(2.0)  # let the final turn close on silence
            await ws.send(json.dumps({"type": "Terminate"}))

        async def recv():
            async for raw in ws:
                m = json.loads(raw)
                now = time.perf_counter()
                if m["type"] == "Begin":
                    print(f"[{now-t0:6.2f}s] Begin id={m['id']}")
                elif m["type"] == "Turn":
                    turns.append(m)
                    if m.get("end_of_turn"):
                        lat = (now - last_voice_t) if last_voice_t else float("nan")
                        finals.append({"turn_order": m["turn_order"], "latency_s": round(lat, 3),
                                       "words": len(m.get("words", [])), "transcript": m["transcript"]})
                        print(f"[{now-t0:6.2f}s] FINAL  +{lat:5.2f}s  {m['transcript']}")
                    else:
                        print(f"[{now-t0:6.2f}s] partial          {m['transcript'][:70]}")
                elif m["type"] == "Termination":
                    print(f"[{now-t0:6.2f}s] Termination audio={m['audio_duration_seconds']}s session={m['session_duration_seconds']}s")
                    return
                elif m["type"] == "Error":
                    print("ERROR", m)

        await asyncio.gather(send(), recv())

    print(f"\nfinals={len(finals)} mode={a.mode} chunk={CHUNK_MS}ms partial_msgs={len(turns) - len(finals)}")
    if a.out:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        new = not os.path.exists(a.out)
        with open(a.out, "a", newline="", encoding="utf-8") as f:
            wr = csv.writer(f)
            if new:
                wr.writerow(["ts", "wav", "mode", "turn_order", "latency_s", "words", "transcript"])
            for r in finals:
                wr.writerow([time.strftime("%Y-%m-%dT%H:%M:%S"), os.path.basename(a.wav), a.mode, r["turn_order"], r["latency_s"], r["words"], r["transcript"]])
        print("appended", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
