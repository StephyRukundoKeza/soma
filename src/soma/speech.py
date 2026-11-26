"""Speech to text. Kinyarwanda uses Digital Umuganda's Whisper model, which runs on this computer;
other languages (and Kinyarwanda when that model is not downloaded) use Gemini.

Recordings are processed once and never stored.
"""

import os
import struct
import time
from functools import lru_cache

import numpy as np

import rag

KINYARWANDA_MODEL = os.environ.get("SOMA_RW_SPEECH_MODEL", "DigitalUmuganda/whisper_small_kinyarwanda")


WINDOW_SECONDS = 30      # Whisper hears 30 seconds at a time; longer recordings are cut into pieces


@lru_cache(maxsize=1)
def kinyarwanda_pipeline():
    import torch
    from transformers import pipeline

    torch.set_num_threads(max(1, os.cpu_count() or 1))     # use every processor core
    pipe = pipeline("automatic-speech-recognition", model=KINYARWANDA_MODEL, device="cpu")
    try:
        # 8-bit weights: about twice as fast on a normal computer, with almost the same accuracy
        pipe.model = torch.quantization.quantize_dynamic(pipe.model, {torch.nn.Linear}, dtype=torch.qint8)
    except Exception as error:
        print(f"Speech model kept at full size: {str(error)[:100]}")
    return pipe


def wav_samples(audio):
    """16-bit mono WAV bytes -> float samples between -1 and 1, and the sample rate.

    Read by hand: the standard wave module imports a module named "chunk", which this
    project's own chunk.py would replace on older Python versions.
    """
    if audio[:4] != b"RIFF" or audio[8:12] != b"WAVE":
        raise ValueError("not a WAV file")
    rate, position, data = 16000, 12, b""
    while position + 8 <= len(audio):
        name, size = audio[position:position + 4], struct.unpack("<I", audio[position + 4:position + 8])[0]
        body = audio[position + 8:position + 8 + size]
        if name == b"fmt ":
            rate = struct.unpack("<I", body[4:8])[0]
        elif name == b"data":
            data = body
        position += 8 + size + (size % 2)
    data = data[:len(data) // 2 * 2]
    return np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0, rate


def kinyarwanda(audio):
    samples, rate = wav_samples(audio)
    options = {"generate_kwargs": {"num_beams": 1, "max_new_tokens": 200}}   # fastest decoding
    if len(samples) > WINDOW_SECONDS * rate:
        options["chunk_length_s"] = WINDOW_SECONDS
    return kinyarwanda_pipeline()({"raw": samples, "sampling_rate": rate}, **options)["text"].strip()


def transcribe(audio, language="en", context=""):
    """Returns (text, engine). Falls back to Gemini if the local Kinyarwanda model is not available."""
    if language == "rw":
        try:
            start = time.time()
            text = kinyarwanda(audio)
            print(f"[speech] Digital Umuganda model: {time.time() - start:.1f} s")
            if text:
                return text, "digital-umuganda-whisper"
        except Exception as error:      # not downloaded, or no transformers: Gemini takes over
            print(f"Kinyarwanda speech model not used: {str(error)[:120]}")
    start = time.time()
    text = rag.transcribe(audio, language, context=context)
    print(f"[speech] Gemini: {time.time() - start:.1f} s")
    return text, "gemini"


def warm_up():
    """Load the Kinyarwanda model in the background so the first learner does not wait."""
    try:
        start = time.time()
        pipe = kinyarwanda_pipeline()
        pipe({"raw": np.zeros(16000, dtype=np.float32), "sampling_rate": 16000})   # first run is the slowest
        print(f"[speech] Kinyarwanda model ready in {time.time() - start:.0f} s")
    except Exception as error:
        print(f"Kinyarwanda speech model not loaded: {str(error)[:120]}")
