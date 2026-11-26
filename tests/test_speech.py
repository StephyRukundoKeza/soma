import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "soma"))

import speech  # noqa: E402


def wav(samples=(0, 16384, -16384)):
    """A tiny 16 kHz mono WAV, built the same way as the web page builds recordings."""
    data = b"".join(struct.pack("<h", s) for s in samples)
    header = (b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt " +
              struct.pack("<IHHIIHH", 16, 1, 1, 16000, 32000, 2, 16) + b"data" + struct.pack("<I", len(data)))
    return header + data


def test_wav_is_read_as_samples_between_minus_one_and_one():
    samples, rate = speech.wav_samples(wav())
    assert rate == 16000 and list(samples) == [0.0, 0.5, -0.5]


def test_kinyarwanda_uses_the_digital_umuganda_model(monkeypatch):
    monkeypatch.setattr(speech, "kinyarwanda", lambda audio: "Ndumva ufite ukuri")
    monkeypatch.setattr(speech.rag, "transcribe", lambda *a, **k: "gemini text")
    assert speech.transcribe(wav(), "rw") == ("Ndumva ufite ukuri", "digital-umuganda-whisper")


def test_gemini_takes_over_when_the_local_model_is_missing(monkeypatch):
    def missing(audio):
        raise OSError("model not downloaded")
    seen = {}
    monkeypatch.setattr(speech, "kinyarwanda", missing)
    monkeypatch.setattr(speech.rag, "transcribe", lambda audio, language, context="": seen.update(context=context) or "Ndumva")
    assert speech.transcribe(wav(), "rw", context="Vuga icyo utekereza") == ("Ndumva", "gemini")
    assert seen["context"] == "Vuga icyo utekereza"


def test_other_languages_use_gemini(monkeypatch):
    monkeypatch.setattr(speech, "kinyarwanda", lambda audio: "should not be used")
    monkeypatch.setattr(speech.rag, "transcribe", lambda *a, **k: "I think so")
    assert speech.transcribe(wav(), "en") == ("I think so", "gemini")
