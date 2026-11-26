"""SOMA's speaking coach: one hard skill, taught step by step, hints before answers."""

import json
import re
from functools import lru_cache

from fluency import for_coach
from index import CHUNKS_FILE
from rag import LANGUAGE_NAMES, SOURCE_LABELS, call_model, ensure_language

SKILL = "Disagreeing politely"

# The learning sequence: each step builds on the one before. It is the same in every
# language, but each language is practised in itself and grounded in its own book.
# "pages": (source, "printed" or "pdf" page number, a word to centre the excerpt on).
LISTENING = ("gscs_s4", "printed", 12, "active listening")
RW_DEBATE = [("kinyarwanda_s4", "printed", 74, "uko bajya impaka"), ("kinyarwanda_s4", "printed", 73, "imyitwarire")]
SW_DEBATE = [("kiswahili_s4", "printed", 149, "kusikiliza maoni"), ("kiswahili_s4", "printed", 141, "mjadala")]
FR_RESPECT = [("french_s4", "printed", 7, "respect mutuel"), ("french_s4", "printed", 52, "débat")]

LEARNING_SEQUENCE = [
    {
        "title": "Listen before you answer",
        "goal": "Show that you heard the other person before giving your own view.",
        "check": "The learner repeats or sums up the other person's point in their own words "
                 "before reacting, without interrupting.",
        "pages": {"en": [LISTENING], "rw": [LISTENING, RW_DEBATE[0]],
                  "sw": [LISTENING, SW_DEBATE[0]], "fr": [LISTENING, FR_RESPECT[1]]},
    },
    {
        "title": "Accept what is right in their view",
        "goal": "Say what you agree with, or why their view makes sense, before disagreeing.",
        "check": "The learner names one good point or reason in the other person's view.",
        "pages": {"en": [("comm_practice", "pdf", 227, "other points of view")],
                  "rw": [RW_DEBATE[0]], "sw": [SW_DEBATE[0]], "fr": [FR_RESPECT[0]]},
    },
    {
        "title": "Soften your words",
        "goal": "Use polite, softening words to disagree.",
        "check": "The learner disagrees using at least one softening word or phrase, with no rude words.",
        "pages": {"en": [("english_s4", "pdf", 71, "politely"), ("english_s4", "pdf", 72, "soften")],
                  "rw": [RW_DEBATE[1]], "sw": [("kiswahili_s4", "printed", 20, "adabu")],
                  "fr": [FR_RESPECT[0], ("french_s4", "printed", 23, "politesse")]},
    },
    {
        "title": "Disagree with the idea, not the person",
        "goal": "Criticise the idea and give a reason, without belittling the person.",
        "check": "The learner gives their view with a reason and does not attack or mock the person.",
        "pages": {"en": [("gscs_s4", "printed", 28, "criticism"), ("gscs_s4", "printed", 38, "assertive")],
                  "rw": RW_DEBATE, "sw": SW_DEBATE, "fr": FR_RESPECT},
    },
    {
        "title": "Formal or informal?",
        "goal": "Choose the right tone: respectful with a teacher or leader, relaxed with a friend.",
        "check": "The learner disagrees in a way that fits who they are speaking to.",
        "pages": {"en": [("english_s4", "pdf", 72, "formal")], "rw": [RW_DEBATE[1]],
                  "sw": [SW_DEBATE[0]], "fr": [FR_RESPECT[0]]},
    },
    {
        "title": "Put it all together",
        "goal": "In a short real situation, listen, accept, soften, give a reason and fit the tone.",
        "check": "In two or three sentences the learner uses most of the earlier steps.",
        "pages": {"en": [LISTENING, ("english_s4", "pdf", 72, "role play")], "rw": RW_DEBATE,
                  "sw": SW_DEBATE, "fr": FR_RESPECT},
    },
]

# Polite phrases and the respectful tone in each language, given to the coach as examples
POLITE_WAYS = {
    "en": "softeners: could, would, I think, I'm not sure, please; respectful tone: could you / would you, "
          "less formal with friends: can / will",
    "rw": "imvugo yoroshya: Mbabarira, Ndumva, Wenda, Simbizi neza ariko, Ese ntibyaba byiza…?, Nyabuneka; "
          "icyubahiro: kubwira mukuru cyangwa mwarimu ukoresheje 'mwe' (urugero: Mwarimu, mwambabarira…)",
    "sw": "maneno ya adabu: Samahani, Nadhani, Labda, Tafadhali, Ningependa kusema; heshima kwa mwalimu "
          "au mkubwa: Shikamoo, Mwalimu, naomba…",
    "fr": "mots qui adoucissent : Excuse-moi, Je pense que, Peut-être que, Je ne suis pas sûr(e), "
          "s'il te plaît ; ton respectueux : vouvoyer un enseignant (Pourriez-vous… s'il vous plaît)",
}

EXCERPT_CHARS = 1200
MAX_HISTORY = 8          # earlier messages sent back to the model
PASSED = re.compile(r"STEP_PASSED:\s*(yes|no)\s*$", re.IGNORECASE)

TUTOR_RULES = """You are SOMA, a patient speaking coach for Senior 4 learners in Rwanda (about 15-17 years old).
Skill: {skill}, practised in {language}.
Current step {number} of {total}: {title}.
Goal of this step: {goal}
The learner passes this step when: {check}
Polite ways of speaking in {language}: {polite}

Book passages for this step (use only these for facts; cite them exactly as labelled; they may be in
another language: use their ideas and explain them in {language}):
{passages}

How to coach:
1. Everything happens in {language}: the situation, the learner's sentences, your feedback and any example.
   If the learner answers in another language, kindly ask them to try again in {language}.
2. Give the learner a short, everyday situation (school, family, friends, sport) and ask them to try. Never show a model answer before they try.
3. When they try, first say what was good. If something is not right yet, give ONE hint: a question or a clue, not the corrected sentence.
4. Only after two tries on the same situation, show one example sentence, explain why it works, and ask them to try again in their own words.
5. Explain mistakes kindly. Never say "wrong" and never use crosses; say "not yet".
6. If the learner's answer was spoken (marked "spoken"), judge how it sounds when said aloud: fluency, pauses, fillers and tone matter, not spelling or punctuation. Name one fluency point using SOMA's measures in simple words.
7. Keep each reply under about 80 words. Do not greet the learner again after your first message.
8. Never ask for personal information such as names, school, phone or address.
9. If the learner asks about something else, say briefly that Ask SOMA can help with that, then return to the task.
10. End every reply with one last line, exactly: STEP_PASSED: yes  or  STEP_PASSED: no
    Say yes only when the learner's latest try meets the pass rule above."""


@lru_cache(maxsize=1)
def load_chunks():
    return json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))


def excerpt(text, focus):
    """A window of the page centred on the focus word, so the useful part is never cut off."""
    start = max(0, text.lower().find(focus.lower()) - EXCERPT_CHARS // 3)
    return text[start:start + EXCERPT_CHARS]


def step_passages(step, language="en"):
    passages = []
    for source, kind, number, focus in step["pages"].get(language, step["pages"]["en"]):
        key = "printed_page" if kind == "printed" else "page"
        matches = [c for c in load_chunks() if c["source"] == source and c.get(key) == number]
        if not matches:
            continue
        best = max(matches, key=lambda c: focus.lower() in c["text"].lower())
        label = SOURCE_LABELS.get(source, source)
        page = f"p. {number}" if kind == "printed" else f"PDF p. {number}"
        passages.append(f"[{label}, {page}]\n{excerpt(best['text'], focus)}")
    return "\n\n".join(passages)


def coach(step_index, message, history=(), language="en", names=(), spoken=None):
    """One turn of practice. history is a list of {"role": "learner"|"soma", "text": ...}.

    spoken = {"seconds", "wpm"} when the answer was recorded with the microphone.
    Returns {"reply", "passed", "step", "total"}; passed=True means the learner may move on
    (shown in green), passed=False means "not yet" (shown in yellow).
    """
    step = LEARNING_SEQUENCE[step_index]
    system = TUTOR_RULES.format(
        skill=SKILL, number=step_index + 1, total=len(LEARNING_SEQUENCE),
        title=step["title"], goal=step["goal"], check=step["check"],
        passages=step_passages(step, language), language=LANGUAGE_NAMES.get(language, "English"),
        polite=POLITE_WAYS.get(language, POLITE_WAYS["en"]))

    lines = [f"{'Learner' if turn['role'] == 'learner' else 'SOMA'}: {turn['text']}"
             for turn in list(history)[-MAX_HISTORY:]]
    if message.strip():
        how = f" (spoken; measured by SOMA: {for_coach(spoken)})" if spoken else ""
        lines.append(f"Learner{how}: {message.strip()}")
    else:
        lines.append("(The learner has just opened this step. Introduce it in one sentence and give the first situation.)")
    reply = call_model("\n".join(lines), system, names)

    match = PASSED.search(reply)
    passed = bool(match) and match.group(1).lower() == "yes" and bool(message.strip())
    reply = ensure_language(PASSED.sub("", reply).strip(), language, names)
    return {"reply": reply, "passed": passed, "step": step_index, "total": len(LEARNING_SEQUENCE)}
