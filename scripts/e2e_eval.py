"""End-to-end latency + safety eval: WAV -> AssemblyAI realtime -> (each final turn) -> Gemini suggestion.

Measures, per final turn: t_stt (last voiced chunk -> end_of_turn) and t_llm (suggest call), total = t_stt + queue wait + t_llm.
Each case warms the model first, the way a real session does; without it every file's first turn is a cold call.
Records only measurements, self-reported commitment flags and id validity. No transcript or model text is persisted.
Receiving STT is independent of model evaluation; total includes model queue wait. Semantic review stays unreviewed.

Usage:
  op run --env-file .env.op -- python -m scripts.e2e_eval samples/sample-01.wav samples/sample-02.wav --min-cases 2 --out docs/eval/e2e.csv
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import math
from pathlib import Path
import os
import statistics
import struct
import sys
import threading
import time
import wave
from urllib.parse import urlencode

import websockets

from app.models import SuggestRequest, Utterance
from app.suggest import GeminiJsonModel, JsonModel, suggest, warmup

WS = "wss://streaming.assemblyai.com/v3/ws"
CHUNK_MS = 100
SILENCE_RMS = 300
CASES = Path(__file__).resolve().parent.parent / "samples" / "cases.json"
# The situation-D cases turn on the memo granting staging authority: judging them against a memo that
# withholds it measures the wrong thing, so the premise comes from the same file as the cases.
PREMISE = json.loads(CASES.read_text(encoding="utf-8"))["premise_ja"]


def rms(pcm: bytes) -> float:
    n = len(pcm) // 2
    return (sum(v * v for v in struct.unpack(f"<{n}h", pcm)) / n) ** 0.5 if n else 0.0


async def run_wav(path: str, model: JsonModel, mode: str, review: list | None = None) -> list[dict]:
    key = os.environ["ASSEMBLYAI_API_KEY"]
    # Match production: app/main.py warms the model in the background when a session starts, so measuring
    # without it charges every first turn a cold call the real user never pays.
    threading.Thread(target=warmup, args=(model,), daemon=True).start()
    with wave.open(path, "rb") as w:
        if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1, 2, 16000):
            w.close()
            raise ValueError("WAV must be mono PCM16 at 16 kHz")
        fpc = 16000 * CHUNK_MS // 1000
        q = urlencode({"speech_model": "universal-3-5-pro", "encoding": "pcm_s16le", "sample_rate": 16000, "mode": mode,
                       "language_codes": "en",
                       "prompt": "English technical meeting between software engineers about delivery dates, environments (staging vs production), scope and approvals."})
        last_voice = None
        turns: list[Utterance] = []
        rows: list[dict] = []
        queue = asyncio.Queue()
        async with websockets.connect(f"{WS}?{q}", additional_headers={"Authorization": key}, max_size=None) as ws:
            async def send():
                nonlocal last_voice
                while True:
                    pcm = w.readframes(fpc)
                    if not pcm:
                        break
                    pcm = pcm.ljust(fpc * 2, b"\0")
                    if rms(pcm) > SILENCE_RMS:
                        last_voice = time.perf_counter()
                    await ws.send(pcm)
                    await asyncio.sleep(CHUNK_MS / 1000)
                await asyncio.sleep(2.0)
                await ws.send(json.dumps({"type": "Terminate"}))

            async def recv():
                async for raw in ws:
                    m = json.loads(raw)
                    if m["type"] == "Turn" and m.get("end_of_turn") and m.get("transcript", "").strip():
                        t_final = time.perf_counter()
                        t_stt = t_final - last_voice if last_voice else float("nan")
                        turns.append(Utterance(id=f"u{len(turns)+1}", text=m["transcript"], t_ms=int(t_final * 1000)))
                        req = SuggestRequest(premise=PREMISE, utterances=turns[-8:])
                        await queue.put((len(turns), t_stt, t_final, req))
                    elif m["type"] == "Termination":
                        break
                await queue.put(None)

            async def evaluate():
                while (item := await queue.get()) is not None:
                    turn, t_stt, t_final, req = item
                    t0 = time.perf_counter()
                    row = {"wav": os.path.basename(path), "turn": turn, "t_stt": round(t_stt, 3),
                           "queue_wait": round(t0 - t_final, 3), "commits": None, "evidence_ok": False,
                           "error": "", "semantic_review": "unreviewed"}
                    try:
                        result = await asyncio.to_thread(suggest, model, req)
                        row.update(commits=result.commits_to_something, evidence_ok=True)
                        if review is not None:
                            review.append({"case": Path(path).stem, "turn": turn, "heard": req.utterances[-1].text,
                                           "summary_ja": result.summary_ja,
                                           "asked_for": result.asked_for, "authority": result.authority,
                                           "next_line_en": result.next_line_en,
                                           "unconfirmed": [u.item for u in result.unconfirmed]})
                    except Exception as exc:
                        # Provider exception messages can contain input text or credentials.
                        row["error"] = type(exc).__name__
                    row["t_llm"] = round(time.perf_counter() - t0, 3)
                    row["total"] = round(t_stt + time.perf_counter() - t_final, 3)
                    rows.append(row)
                    print(f"  turn={turn} total={row['total']:.2f}s evidence_ok={row['evidence_ok']} error={row['error']}")

            tasks = [asyncio.create_task(fn()) for fn in (send, recv, evaluate)]
            try:
                await asyncio.wait_for(asyncio.gather(*tasks), timeout=w.getnframes() / 16000 + 120)
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                try:
                    await ws.send(json.dumps({"type": "Terminate"}))
                except websockets.ConnectionClosed:
                    pass
                w.close()
        return rows


def summarize(rows: list[dict], expected_cases: int, min_cases: int) -> dict:
    ok = [r for r in rows if r["evidence_ok"] and not r["error"]]
    totals = sorted(r["total"] for r in ok if math.isfinite(r["total"]))
    cases = len({r["wav"] for r in ok})
    fast = sum(t <= 3.0 for t in totals)
    commits = sum(bool(r["commits"]) for r in ok)
    passed = (cases == expected_cases and cases >= min_cases and len(ok) == len(rows)
              and len(totals) == len(rows) and bool(rows) and not commits and fast / len(rows) >= 0.9)
    return {"measurement_gate": "PASS" if passed else "HOLD", "cases": cases, "turns": len(rows),
            "evidence_ok": len(ok), "commits": commits, "within_3s": fast,
            "median": statistics.median(totals) if totals else None,
            "p90": totals[math.ceil(len(totals) * 0.9) - 1] if totals else None,
            "semantic_review": "unreviewed"}


async def main() -> int:
    ap = argparse.ArgumentParser(description="Audio measurements only; semantic correctness needs a separate review.")
    ap.add_argument("wavs", nargs="+")
    ap.add_argument("--mode", choices=["min_latency", "balanced", "max_accuracy"], default="min_latency")
    ap.add_argument("--min-cases", type=int, default=20, help="Distinct audio files required (default: 20)")
    ap.add_argument("--out", default="")
    ap.add_argument("--review", default="", help="write suggestions to this JSON for the human semantic pass "
                                                 "(holds model text, so keep it out of the repo)")
    a = ap.parse_args()
    paths = [Path(p).resolve() for p in a.wavs]
    if a.min_cases < 1 or len(set(paths)) != len(paths) or len({p.name for p in paths}) != len(paths):
        ap.error("Use distinct WAV paths and basenames; --min-cases must be positive")
    if len(paths) < a.min_cases:
        ap.error(f"Need {a.min_cases} distinct audio cases; received {len(paths)}. No provider calls made.")
    for p in paths:
        with wave.open(str(p), "rb") as wav:
            if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) != (1, 2, 16000):
                ap.error("Every WAV must be mono PCM16 at 16 kHz")
    # Never append measurements to legacy CSVs that contain conversation text.
    if a.out and Path(a.out).exists():
        ap.error("--out must name a new file")
    model = GeminiJsonModel(project=os.environ["GOOGLE_CLOUD_PROJECT"], location=os.environ.get("MSA_GEMINI_LOCATION", "global"),
                            model=os.environ.get("MSA_GEMINI_MODEL", "gemini-2.5-flash-lite"))
    rows: list[dict] = []
    review: list[dict] | None = [] if a.review else None
    for p in paths:
        rows += await run_wav(str(p), model, a.mode, review)
    if review is not None:
        Path(a.review).parent.mkdir(parents=True, exist_ok=True)
        Path(a.review).write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = summarize(rows, len(paths), a.min_cases)
    print(json.dumps(summary, ensure_ascii=False, allow_nan=False))
    if a.out and rows:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        with open(a.out, "x", newline="", encoding="utf-8") as f:
            wr = csv.DictWriter(f, fieldnames=["ts", "mode", *rows[0].keys()])
            wr.writeheader()
            for r in rows:
                wr.writerow({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": a.mode, **r})
    return 0 if summary["measurement_gate"] == "PASS" else 1


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except Exception as exc:
        print(f"Evaluation failed: {type(exc).__name__}", file=sys.stderr)
        sys.exit(1)
