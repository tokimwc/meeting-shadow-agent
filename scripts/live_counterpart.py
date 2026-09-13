"""Hold a conversation between a pushy counterpart and the card, through the real pipeline.

The demo needs a counterpart that argues back, and a WAV cannot: it plays on regardless of what the
engineer said. So the counterpart is a model given one of the roles in
docs/usability/live-counterpart.md, and the engineer says exactly what the card says. Every
counterpart line is synthesised, streamed through AssemblyAI realtime and turned into a suggestion by
the same `suggest()` the service runs; the engineer's reply is that suggestion's `next_line_en`,
synthesised in a second voice. When the product refuses, the card is empty and the engineer has
nothing from it, and the record says so rather than inventing a line.

What this is not: a test of whether a person can use the card. There is no person in it. The engineer
here reads every card perfectly and instantly, which no human does, so nothing it produces is evidence
about usability. It shows what the product does against a counterpart that reacts.

The counterpart is gemini-2.5-flash, not the Flash-Lite that writes the cards, so the two sides are not
the same model agreeing with itself.

  op run --env-file .env.op -- python -m scripts.live_counterpart diego --out samples/live/diego
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
import wave
from pathlib import Path
from urllib.parse import urlencode

import websockets

from app.models import SuggestRequest, Utterance
from app.suggest import GeminiJsonModel, suggest
from scripts.make_narration import PROJECT, token

ROOT = Path(__file__).resolve().parent.parent
ROLES_DOC = ROOT / "docs" / "usability" / "live-counterpart.md"
PREMISE = json.loads((ROOT / "samples" / "cases.json").read_text(encoding="utf-8"))["premise_ja"]
WS = "wss://streaming.assemblyai.com/v3/ws"
TTS = "https://texttospeech.googleapis.com/v1/text:synthesize"
CHUNK_MS = 100
# Three speakers in one video: the narrator is Charon, so neither side of the call may be.
VOICE = {"counterpart": "en-US-Chirp3-HD-Orus", "engineer": "en-US-Chirp3-HD-Kore"}
# When the card is empty there is nothing from the product to say. This line is the engineer
# stalling, and is recorded as exactly that.
STALL = "Sorry, give me one moment."
GOODBYE = re.compile(r"\b(bye|talk soon|speak soon|have a (good|great)|thanks for your time|take care)\b", re.I)


def roles() -> dict[str, str]:
    # One source for the roles: the procedure doc a person would paste from.
    found = re.findall(r"```\n(You are (\w+), .+?)\n```", ROLES_DOC.read_text(encoding="utf-8"), re.S)
    return {name.lower(): text for text, name in found}


def synthesize(text: str, voice: str, access: str, path: Path) -> float:
    import urllib.request
    body = json.dumps({"input": {"text": text}, "voice": {"languageCode": "en-US", "name": voice},
                       "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 16000}}).encode()
    req = urllib.request.Request(TTS, data=body, headers={
        "Authorization": f"Bearer {access}", "x-goog-user-project": PROJECT, "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        import base64
        path.write_bytes(base64.b64decode(json.loads(r.read())["audioContent"]))
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


async def transcribe(path: Path) -> list[tuple[str, float]]:
    """Final turns for one line, with the seconds from its last audio to each end_of_turn."""
    q = urlencode({"speech_model": "universal-3-5-pro", "encoding": "pcm_s16le", "sample_rate": 16000,
                   "mode": "min_latency", "language_codes": "en",
                   "prompt": "English technical meeting between software engineers about delivery dates, "
                             "environments (staging vs production), scope and approvals."})
    out: list[tuple[str, float]] = []
    sent_last = None
    with wave.open(str(path), "rb") as w:
        fpc = 16000 * CHUNK_MS // 1000
        async with websockets.connect(f"{WS}?{q}", additional_headers={"Authorization": os.environ["ASSEMBLYAI_API_KEY"]},
                                      max_size=None) as ws:
            async def send():
                nonlocal sent_last
                while pcm := w.readframes(fpc):
                    await ws.send(pcm.ljust(fpc * 2, b"\0"))
                    await asyncio.sleep(CHUNK_MS / 1000)
                sent_last = time.perf_counter()
                silence = b"\0" * fpc * 2
                for _ in range(20):  # 2 s of room tone, so the end of turn is decided by the model, not by EOF
                    await ws.send(silence)
                    await asyncio.sleep(CHUNK_MS / 1000)
                await ws.send(json.dumps({"type": "Terminate"}))

            async def recv():
                async for raw in ws:
                    m = json.loads(raw)
                    if m["type"] == "Turn" and m.get("end_of_turn") and m.get("transcript", "").strip():
                        # A turn that closes while the line is still being sent has no end-of-audio to be
                        # timed against; only a turn after the last chunk carries a latency.
                        out.append((m["transcript"], time.perf_counter() - sent_last if sent_last else None))
                    elif m["type"] == "Termination":
                        return

            await asyncio.wait_for(asyncio.gather(send(), recv()), timeout=60)
    return out


class Counterpart:
    def __init__(self, role: str) -> None:
        from google import genai
        from google.genai import types
        self.t = types
        self.client = genai.Client(enterprise=True, project=os.environ["GOOGLE_CLOUD_PROJECT"],
                                   location=os.environ.get("MSA_GEMINI_LOCATION", "global"),
                                   http_options=types.HttpOptions(api_version="v1"))
        self.role = role
        self.history = [types.Content(role="user", parts=[types.Part(text="(The call has connected.)")])]

    def say(self) -> str:
        t = self.t
        r = self.client.models.generate_content(
            model="gemini-2.5-flash", contents=self.history,
            config=t.GenerateContentConfig(
                system_instruction=self.role, temperature=0.9, max_output_tokens=400,
                # A thinking model spends output tokens on thinking first; with none left the line is cut off.
                thinking_config=t.ThinkingConfig(thinking_budget=0)))
        line = (r.text or "").strip().strip('"')
        self.history.append(t.Content(role="model", parts=[t.Part(text=line)]))
        return line

    def hear(self, line: str) -> None:
        self.history.append(self.t.Content(role="user", parts=[self.t.Part(text=line)]))


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("role", choices=sorted(roles()))
    ap.add_argument("--out", required=True)
    ap.add_argument("--turns", type=int, default=9, help="most counterpart lines before stopping")
    a = ap.parse_args()

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    access = token()
    cards = GeminiJsonModel(project=os.environ["GOOGLE_CLOUD_PROJECT"],
                            location=os.environ.get("MSA_GEMINI_LOCATION", "global"),
                            model=os.environ.get("MSA_GEMINI_MODEL", "gemini-2.5-flash-lite"))
    them = Counterpart(roles()[a.role])
    utterances: list[Utterance] = []
    record = {"role": a.role, "premise": PREMISE, "voices": VOICE, "exchanges": []}

    for i in range(1, a.turns + 1):
        line = them.say()
        wav = out / f"{i:02d}-counterpart.wav"
        secs = synthesize(line, VOICE["counterpart"], access, wav)
        heard = await transcribe(wav)
        ex = {"n": i, "counterpart": line, "counterpart_seconds": round(secs, 2), "turns": []}
        card = None
        for text, t_stt in heard:
            utterances.append(Utterance(id=f"u{len(utterances) + 1}", text=text, t_ms=len(utterances) * 4000))
            t0 = time.perf_counter()
            turn = {"heard": text, "t_stt": None if t_stt is None else round(t_stt, 3)}
            try:
                card = suggest(cards, SuggestRequest(premise=PREMISE, utterances=utterances[-8:]))
                turn.update(authority=card.authority, asked_for=card.asked_for, next_line_en=card.next_line_en,
                            next_line_ja=card.next_line_ja, summary_ja=card.summary_ja,
                            unconfirmed=[u.item for u in card.unconfirmed], evidence_ids=card.evidence_ids,
                            commits=card.commits_to_something)
            except Exception as exc:  # a refusal is a real outcome: the engineer gets no card
                card = None
                turn["refused"] = type(exc).__name__
            turn["t_llm"] = round(time.perf_counter() - t0, 3)
            ex["turns"].append(turn)

        reply = card.next_line_en if card else STALL
        ex["engineer"] = reply
        ex["engineer_from_card"] = card is not None
        ex["engineer_seconds"] = round(synthesize(reply, VOICE["engineer"], access, out / f"{i:02d}-engineer.wav"), 2)
        record["exchanges"].append(ex)
        them.hear(reply)

        last = ex["turns"][-1] if ex["turns"] else {}
        print(f"\n[{i}] THEM   {line}")
        for tn in ex["turns"]:
            print(f"      heard  {tn['heard']}")
            print(f"      card   {tn.get('authority', 'REFUSED ' + tn.get('refused', ''))}"
                  f"  stt {'mid-line' if tn['t_stt'] is None else format(tn['t_stt'], '.2f') + 's'}  llm {tn['t_llm']:.2f}s")
        print(f"    ENGINEER {reply}{'' if card else '   (no card)'}")
        if GOODBYE.search(line) and i > 2:
            break

    (out / "conversation.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{len(record['exchanges'])} exchanges -> {out}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(asyncio.run(main()))
