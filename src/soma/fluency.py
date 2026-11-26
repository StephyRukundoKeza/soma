"""Fluency measures for one spoken answer, counted by SOMA itself (not guessed by a model).

From the recording: speaking time, pauses (silences of 0.7 s or more inside the answer) and long pauses (2 s or more).
From the transcript: speed, fillers ("eee", "umm", "euh"...), repeated words and the polite phrases taught in the lessons.

Each language has its own fillers, taught phrases and comfortable speed: Kinyarwanda and Kiswahili join many
pieces into one long word, so the same message has fewer words per minute than in English or French.
These speed bands are starting points from general speech-rate research and will be adjusted with real learners.
"""

import re

import numpy as np

FRAME_SECONDS = 0.03
PAUSE_SECONDS = 0.7
LONG_PAUSE_SECONDS = 2.0

LANGUAGE_RULES = {
    "en": {
        "speed": (100, 160),
        "fillers": {"um", "umm", "uh", "uhh", "er", "erm", "hmm", "ah"},
        "filler_phrases": ["you know", "i mean"],
        "phrases": ["i think", "i see your point", "i understand", "i'm not sure", "i am not sure", "could you",
                    "would you", "may i", "please", "i agree", "however", "with respect"],
    },
    "rw": {
        "speed": (60, 115),
        "fillers": {"eee", "ee", "ehh", "eh", "aaa", "mmm", "hmm", "nyine"},
        "filler_phrases": [],
        "phrases": ["mbabarira", "ndumva", "wenda", "simbizi neza", "ese ntibyaba byiza", "nyabuneka",
                    "ndakumva", "ndemera", "ariko", "mwambabarira", "murakoze"],
    },
    "sw": {
        "speed": (80, 135),
        "fillers": {"eee", "ee", "ehh", "eh", "aaa", "mmm", "hmm", "yaani"},
        "filler_phrases": [],
        "phrases": ["samahani", "nadhani", "labda", "tafadhali", "ningependa", "naomba", "nakubaliana",
                    "lakini", "kwa heshima", "asante"],
    },
    "fr": {
        "speed": (100, 165),
        "fillers": {"euh", "heu", "hum", "bah", "ben", "hein"},
        "filler_phrases": ["tu vois", "en fait"],
        "phrases": ["excuse-moi", "excusez-moi", "je pense que", "peut-être", "je ne suis pas sûr",
                    "je ne suis pas sûre", "s'il te plaît", "s'il vous plaît", "pourriez-vous", "je comprends",
                    "je suis d'accord", "cependant"],
    },
}
LONG_SOUND = re.compile(r"^(e{2,}h*|a{2,}h*|m{2,}|h+m+|u+m+|e+r+m*|eu+h+)$")   # "eeee", "mmm", "uhm"...
GOOD = {"pauses_per_min": 6, "fillers_per_100": 5}


def words_of(text):
    return re.findall(r"[\w'’-]+", text.lower().replace("’", "'"))


def speech_frames(samples, rate):
    """True for each 30 ms frame that contains speech (energy above an adaptive noise threshold)."""
    size = max(1, int(rate * FRAME_SECONDS))
    count = len(samples) // size
    if count == 0:
        return np.zeros(0, dtype=bool)
    energy = np.sqrt(np.mean(samples[:count * size].reshape(count, size) ** 2, axis=1))
    floor, loud = np.percentile(energy, 10), np.percentile(energy, 95)
    return energy > max(0.008, floor + 0.2 * (loud - floor))


def audio_measures(samples, rate):
    frames = speech_frames(samples, rate)
    if not frames.any():
        return {"speaking_seconds": 0.0, "pauses": 0, "long_pauses": 0}
    first, last = np.argmax(frames), len(frames) - 1 - np.argmax(frames[::-1])
    inside = frames[first:last + 1]
    pauses, long_pauses, run = 0, 0, 0
    for is_speech in list(inside) + [True]:
        if not is_speech:
            run += 1
            continue
        if run * FRAME_SECONDS >= PAUSE_SECONDS:
            pauses += 1
            long_pauses += run * FRAME_SECONDS >= LONG_PAUSE_SECONDS
        run = 0
    return {"speaking_seconds": round(float(inside.sum()) * FRAME_SECONDS, 1), "pauses": pauses,
            "long_pauses": int(long_pauses)}


def text_measures(text, language):
    rules = LANGUAGE_RULES.get(language, LANGUAGE_RULES["en"])
    words = words_of(text)
    lowered = " ".join(words)
    fillers = sum(1 for w in words if w in rules["fillers"] or LONG_SOUND.match(w))
    fillers += sum(lowered.count(p) for p in rules["filler_phrases"])
    repeats = sum(1 for a, b in zip(words, words[1:]) if a == b and a not in rules["fillers"])
    used = [p for p in rules["phrases"] if re.search(rf"(^|\s){re.escape(p)}(\s|$)", lowered)]
    return {"words": len(words), "fillers": fillers, "repeats": repeats, "phrases": used}


def measure(samples, rate, text, language):
    """All measures for one answer, with a green/yellow judgement for each."""
    rules = LANGUAGE_RULES.get(language, LANGUAGE_RULES["en"])
    seconds = max(len(samples) / rate, 0.1)
    audio = audio_measures(samples, rate)
    words = text_measures(text, language)
    minutes = seconds / 60
    wpm = round(words["words"] / minutes) if words["words"] else 0
    pauses_per_min = round(audio["pauses"] / minutes, 1)
    fillers_per_100 = round(100 * words["fillers"] / words["words"], 1) if words["words"] else 0.0
    low, high = rules["speed"]
    return {
        "seconds": round(seconds, 1), "wpm": wpm, "target_wpm": [low, high],
        "speaking_ratio": round(audio["speaking_seconds"] / seconds, 2),
        "pauses": audio["pauses"], "long_pauses": audio["long_pauses"], "pauses_per_min": pauses_per_min,
        "fillers": words["fillers"], "fillers_per_100": fillers_per_100, "repeats": words["repeats"],
        "phrases": words["phrases"],
        "checks": {
            "speed": "green" if low <= wpm <= high else "yellow",
            "pauses": "green" if pauses_per_min <= GOOD["pauses_per_min"] and audio["long_pauses"] == 0 else "yellow",
            "fillers": "green" if fillers_per_100 <= GOOD["fillers_per_100"] else "yellow",
            "phrases": "green" if words["phrases"] else "yellow",
        },
    }


def for_coach(m):
    """A short line describing the measures, for the tutor's instructions."""
    low, high = m["target_wpm"]
    phrases = ", ".join(m["phrases"]) or "none"
    return (f"spoken for {m['seconds']:.0f} s; speed {m['wpm']} words per minute (comfortable range {low}-{high}); "
            f"{m['pauses']} pauses ({m['long_pauses']} longer than 2 s); {m['fillers']} fillers; "
            f"{m['repeats']} repeated words; taught polite phrases used: {phrases}")
