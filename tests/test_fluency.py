import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "soma"))

import numpy as np  # noqa: E402

import fluency  # noqa: E402

RATE = 16000


def speech_with_pauses(parts):
    """parts: list of (seconds, loud). Loud parts are a tone (speech), quiet parts near-silence."""
    rng = np.random.default_rng(0)
    chunks = []
    for seconds, loud in parts:
        n = int(seconds * RATE)
        t = np.arange(n) / RATE
        chunks.append(0.3 * np.sin(2 * np.pi * 220 * t) if loud else 0.002 * rng.standard_normal(n))
    return np.concatenate(chunks).astype(np.float32)


def test_pauses_and_long_pauses_are_counted_from_the_recording():
    samples = speech_with_pauses([(0.5, False), (2, True), (1.0, False), (2, True), (2.5, False), (2, True), (0.3, False)])
    audio = fluency.audio_measures(samples, RATE)
    assert audio["pauses"] == 2 and audio["long_pauses"] == 1     # silence at the start and end is not a pause
    assert 5.5 <= audio["speaking_seconds"] <= 6.5


def test_short_breaths_are_not_pauses():
    samples = speech_with_pauses([(2, True), (0.3, False), (2, True)])
    assert fluency.audio_measures(samples, RATE)["pauses"] == 0


def test_kinyarwanda_fillers_repeats_and_taught_phrases():
    words = fluency.text_measures("Eee ndumva ufite ukuri ariko ariko wenda eeee ikoranabuhanga rifasha", "rw")
    assert words["fillers"] == 2 and words["repeats"] == 1
    assert words["phrases"] == ["ndumva", "wenda", "ariko"]


def test_each_language_has_its_own_fillers_and_phrases():
    assert fluency.text_measures("Euh je pense que c'est vrai, euh", "fr")["fillers"] == 2
    assert fluency.text_measures("Euh je pense que", "fr")["phrases"] == ["je pense que"]
    assert fluency.text_measures("Yaani nadhani ni kweli", "sw") == {"words": 4, "fillers": 1, "repeats": 0, "phrases": ["nadhani"]}
    assert fluency.text_measures("Um I think, you know, it is fine", "en")["fillers"] == 2


def test_speed_is_judged_against_the_languages_own_range():
    samples = speech_with_pauses([(30, True)])                      # 30 seconds
    text = " ".join(["ijambo"] * 40)                                # 80 words per minute
    assert fluency.measure(samples, RATE, text, "rw")["checks"]["speed"] == "green"    # fine for Kinyarwanda
    assert fluency.measure(samples, RATE, text, "en")["checks"]["speed"] == "yellow"   # slow for English


def test_the_coach_gets_the_numbers_in_one_line():
    m = fluency.measure(speech_with_pauses([(10, True)]), RATE, "Ndumva ufite ukuri", "rw")
    line = fluency.for_coach(m)
    assert "speed 18 words per minute (comfortable range 60-115)" in line and "ndumva" in line
