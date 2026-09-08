import asyncio
import io
import json
import wave

from scripts import e2e_eval as ev


def test_measurement_gate_requires_cases_and_handles_empty_errors_and_p90():
    assert ev.summarize([], 20, 20)["measurement_gate"] == "HOLD"
    rows = [dict(wav=f"case-{i}", evidence_ok=True, error="", commits=False, total=i / 10) for i in range(1, 21)]
    result = ev.summarize(rows, 20, 20)
    assert result["measurement_gate"] == "PASS" and result["p90"] == 1.8
    assert result["semantic_review"] == "unreviewed"
    assert ev.summarize(rows[:3], 3, 20)["measurement_gate"] == "HOLD"
    rows[-1]["error"] = "ValueError"
    assert ev.summarize(rows, 20, 20)["measurement_gate"] == "HOLD"
    rows[-1].update(error="", total=float("nan"))
    assert ev.summarize(rows, 20, 20)["measurement_gate"] == "HOLD"


def test_audio_eval_redacts_errors_and_terminates(monkeypatch, capsys):
    audio = io.BytesIO()
    with wave.open(audio, "wb") as w:
        w.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        w.writeframes(b"\x01\x01" * 1600)

    class Socket:
        sent = []
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def send(self, data): self.sent.append(data)
        async def __aiter__(self):
            yield json.dumps(dict(type="Turn", end_of_turn=True, transcript="private conversation"))
            yield json.dumps(dict(type="Termination"))

    class BrokenModel:
        def generate_json(self, **kwargs): raise ValueError("private conversation and credential")

    audio.seek(0)
    open_wave = wave.open
    monkeypatch.setattr(ev.wave, "open", lambda *args: open_wave(audio, "rb"))
    socket = Socket()
    monkeypatch.setenv("ASSEMBLYAI_API_KEY", "test-only")
    monkeypatch.setattr(ev.websockets, "connect", lambda *args, **kwargs: socket)
    rows = asyncio.run(ev.run_wav("case.wav", BrokenModel(), "min_latency"))
    assert rows[0]["error"] == "ValueError"
    assert "private" not in json.dumps(rows) + capsys.readouterr().out
    assert any(isinstance(x, str) and json.loads(x)["type"] == "Terminate" for x in socket.sent)
