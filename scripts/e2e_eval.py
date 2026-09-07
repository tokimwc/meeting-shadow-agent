"""End-to-end latency + safety eval: WAV -> AssemblyAI realtime -> (each final turn) -> Gemini suggestion.

Measures, per final turn: t_stt (last voiced chunk -> end_of_turn) and t_llm (suggest call), total = t_stt + t_llm.
Also records commits_to_something and whether the evidence ids were valid (suggest() raises otherwise).

Usage:
  op run --env-file .env.op -- python scripts/e2e_eval.py samples/sample-01.wav samples/sample-02.wav --out docs/eval/e2e.csv
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import statistics
import struct
import sys
import time
import wave
from urllib.parse import urlencode

import websockets

from app.models import SuggestRequest, Utterance
from app.suggest import GeminiJsonModel, suggest

WS = "wss://streaming.assemblyai.com/v3/ws"
CHUNK_MS = 100
SILENCE_RMS = 300
PREMISE = "自分は実装担当。本番反映・納期・スコープの約束には社内確認が必要。"


def rms(pcm: bytes) -> float:
    n = len(pcm) // 2
    return (sum(v * v for v in struct.unpack(f"<{n}h", pcm)) / n) ** 0.5 if n else 0.0


async def run_wav(path: str, model: GeminiJsonModel, mode: str) -> list[dict]:
    key = os.environ["ASSEMBLYAI_API_KEY"]
    w = wave.open(path, "rb")
    assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, 16000)
    fpc = 16000 * CHUNK_MS // 1000
    q = urlencode({"speech_model": "universal-3-5-pro", "encoding": "pcm_s16le", "sample_rate": 16000, "mode": mode,
                   "language_codes": "en",
                   "prompt": "English technical meeting between software engineers about delivery dates, environments (staging vs production), scope and approvals."})
    last_voice = None
    turns: list[Utterance] = []
    rows: list[dict] = []
    async with websockets.connect(f"{WS}?{q}", additional_headers={"Authorization": key}, max_size=None) as ws:
        async def send():
            nonlocal last_voice
            while True:
                pcm = w.readframes(fpc)
                if not pcm:
                    break
                if rms(pcm) > SILENCE_RMS:
                    last_voice = time.perf_counter()
                await ws.send(pcm)
                await asyncio.sleep(CHUNK_MS / 1000)
            await asyncio.sleep(2.0)
            await ws.send(json.dumps({"type": "Terminate"}))

        async def recv():
            async for raw in ws:
                m = json.loads(raw)
                if m["type"] == "Turn" and m.get("end_of_turn"):
                    t_final = time.perf_counter()
                    t_stt = t_final - last_voice if last_voice else float("nan")
                    turns.append(Utterance(id=f"u{len(turns)+1}", text=m["transcript"], t_ms=int(t_final * 1000)))
                    req = SuggestRequest(premise=PREMISE, utterances=turns[-8:])
                    t0 = time.perf_counter()
                    try:
                        s = await asyncio.to_thread(suggest, model, req)
                        t_llm = time.perf_counter() - t0
                        rows.append({"wav": os.path.basename(path), "turn": len(turns), "transcript": m["transcript"],
                                     "t_stt": round(t_stt, 3), "t_llm": round(t_llm, 3), "total": round(t_stt + t_llm, 3),
                                     "commits": s.commits_to_something, "evidence_ok": True,
                                     "next_en": s.next_line_en})
                        print(f"  u{len(turns)} stt={t_stt:.2f} llm={t_llm:.2f} total={t_stt+t_llm:.2f} commits={s.commits_to_something} | {m['transcript'][:60]}")
                    except Exception as e:  # evidence violation or provider error: counted as a failure, run continues
                        t_llm = time.perf_counter() - t0
                        rows.append({"wav": os.path.basename(path), "turn": len(turns), "transcript": m["transcript"],
                                     "t_stt": round(t_stt, 3), "t_llm": round(t_llm, 3), "total": round(t_stt + t_llm, 3),
                                     "commits": None, "evidence_ok": False, "next_en": f"ERROR {type(e).__name__}: {str(e)[:120]}"})
                        print(f"  u{len(turns)} ERROR {type(e).__name__}: {str(e)[:120]}")
                elif m["type"] == "Termination":
                    return
        await asyncio.gather(send(), recv())
    return rows


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("wavs", nargs="+")
    ap.add_argument("--mode", default="min_latency")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    model = GeminiJsonModel(project=os.environ["GOOGLE_CLOUD_PROJECT"], location=os.environ.get("MSA_GEMINI_LOCATION", "global"),
                            model=os.environ.get("MSA_GEMINI_MODEL", "gemini-2.5-flash-lite"))
    rows: list[dict] = []
    for p in a.wavs:
        print(p)
        rows += await run_wav(p, model, a.mode)
    ok = [r for r in rows if r["evidence_ok"]]
    totals = [r["total"] for r in ok]
    print(f"\ncases={len(rows)} evidence_ok={len(ok)} commits={sum(1 for r in ok if r['commits'])} "
          f"total<=3s: {sum(1 for t in totals if t <= 3.0)}/{len(totals)} median={statistics.median(totals):.2f}s "
          f"p90={sorted(totals)[int(len(totals)*0.9)-1]:.2f}s max={max(totals):.2f}s")
    if a.out:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        new = not os.path.exists(a.out)
        with open(a.out, "a", newline="", encoding="utf-8") as f:
            wr = csv.DictWriter(f, fieldnames=["ts", "mode", *rows[0].keys()])
            if new:
                wr.writeheader()
            for r in rows:
                wr.writerow({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": a.mode, **r})
        print("appended", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
