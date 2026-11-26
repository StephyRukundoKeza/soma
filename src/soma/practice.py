"""Adaptive speaking practice: every task is created for the learner's level, never written in advance.

Difficulty goes from 1 to 9 and maps to three levels:
  Level 1 (1-3) guided: the task gives starter words or a sentence frame, and a hint after every try.
  Level 2 (4-6) partial help: one key word at most in the task, a hint only after a try that is not yet right.
  Level 3 (7-9) free speaking: no help in the task; feedback first, a hint only on the second try.
Inside a level, each step asks for a longer, harder answer.

The rule, after each finished task: two greens in a row move one step up;
two yellows in a row move one step down, which gives more help.
Tasks rotate between three scenarios: debate, interview and presentation.
"""

import random
import re

from curriculum import find_unit, unit_passages, units
from fluency import for_coach
from rag import LANGUAGE_NAMES, call_model, ensure_language
from tutor import POLITE_WAYS

MIN_DIFFICULTY, MAX_DIFFICULTY = 1, 9
MAX_TRIES = 3
GREENS_TO_MOVE_UP = 2
YELLOWS_FOR_MORE_HELP = 2
PLACEMENT_DIFFICULTIES = [2, 5, 8]          # one task from each level
START_AFTER_PLACEMENT = [1, 3, 5, 7]        # by number of placement tasks passed (0-3)
SCENARIOS = ["debate", "interview", "presentation"]
PASSED = re.compile(r"TASK_PASSED:\s*(yes|no)\s*$", re.IGNORECASE)

SCENARIO_GUIDE = {
    "debate": "a debate: the learner takes a side on a question from the unit and answers the other side politely",
    "interview": "an interview: the learner answers questions from an interviewer (a teacher, a journalist, an employer "
                 "or a school leader) about the unit's theme",
    "presentation": "a presentation: the learner presents an idea from the unit to a group (class, family meeting, "
                    "school assembly or community meeting)",
}

LEVEL_HELP = {
    1: "Level 1, guided: include two or three starter words or a sentence frame the learner can complete.",
    2: "Level 2, partial help: include at most one key word or idea to use; no sentence frame.",
    3: "Level 3, free speaking: give no words or frames; the learner organises the answer alone.",
}

LENGTH_GUIDE = {
    1: "one short sentence", 2: "one or two sentences", 3: "two sentences",
    4: "three sentences with one reason", 5: "three or four sentences with a reason and an example",
    6: "four sentences with reasons and a polite answer to an opposite view",
    7: "a short talk of five or six sentences", 8: "a talk of about one minute (six to eight sentences)",
    9: "a talk of about one minute on a sensitive or unexpected point, then one follow-up question to answer",
}

HINT_POLICY = {
    1: "Give ONE hint after every try that is not yet right: a starter word or a question, never the full answer.",
    2: "Give ONE hint only if the try is not yet right: a question or a clue, never the corrected answer.",
    3: "On the first try, give feedback only and ask for another try; give ONE hint only on the second try.",
}


def level_of(difficulty):
    return (max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, difficulty)) - 1) // 3 + 1


def is_green(passed, tries):
    """Green: passed before the worked example was needed. Yellow: not yet."""
    return passed and tries < MAX_TRIES


def next_step(difficulty, streak, passed, tries):
    """Apply the rule after a finished task. streak > 0 counts greens in a row, < 0 counts yellows.

    Returns (new_difficulty, new_streak)."""
    if is_green(passed, tries):
        streak = streak + 1 if streak > 0 else 1
        if streak >= GREENS_TO_MOVE_UP and difficulty < MAX_DIFFICULTY:
            return difficulty + 1, 0
        return difficulty, streak
    streak = streak - 1 if streak < 0 else -1
    if -streak >= YELLOWS_FOR_MORE_HELP and difficulty > MIN_DIFFICULTY:
        return difficulty - 1, 0
    return difficulty, streak


def scenario_for(recent):
    return SCENARIOS[len(recent) % len(SCENARIOS)]


TASK_RULES = """You create speaking tasks for SOMA, a speaking coach for Senior 4 learners in Rwanda (about 15-17 years old).
Write ONE task in {language}, for a learner practising speaking {language}.
Topic: the book unit "{unit}". Use the book passages below for the theme and ideas.
Scenario: {scenario}.
Difficulty {difficulty} of 9. {level_help}
Ask for: {length}.
Polite ways of speaking in {language}: {polite}

Book passages:
{passages}

Rules:
- Set the scene in one or two sentences, then say exactly what the learner should say.
- Write only the task, addressed to the learner, in at most 70 words. No greeting, no answer, no example answer.
- Make it different from these recent tasks: {recent}
- Never ask for personal information such as names, school, phone or address."""

ASSESS_RULES = """You are SOMA, a patient speaking coach for Senior 4 learners in Rwanda (about 15-17 years old).
The learner is practising speaking {language}. Everything you write is in {language}.
Task (difficulty {difficulty} of 9, level {level}): {task}
This is try {tries} of {max_tries}.
Polite ways of speaking in {language}: {polite}

Judge the learner's latest answer on: doing what the task asks, the length the task asks for, correct {language},
clarity, and a polite tone that fits the listener.{spoken_rule}

How to reply:
1. First say what was good.
2. If the task is not done yet: {hint_policy}
   On the last try, show one short example answer and explain why it works.
3. If the learner answered in another language, kindly ask them to answer in {language}.
4. Explain mistakes kindly; never say "wrong"; say "not yet".
5. At most about 90 words. No greeting. Never ask for personal information.
6. End with one last line, exactly: TASK_PASSED: yes  or  TASK_PASSED: no"""

SPOKEN_RULE = ("\nThe answer was spoken. Measured by SOMA: {measures}.\n"
               "Judge fluency too: a speed inside the comfortable range, few long pauses, few fillers and the taught "
               "polite phrases. In your reply, name ONE fluency point to improve (or praise), using these numbers in "
               "simple words. Ignore spelling and punctuation: the text was written down from speech.")


def _language_name(language):
    return LANGUAGE_NAMES.get(language, "English")


def new_task(language, unit_id, difficulty, recent=(), names=(), scenario=None):
    unit = find_unit(language, unit_id)
    scenario = scenario or scenario_for(recent)
    system = TASK_RULES.format(
        language=_language_name(language), unit=unit["title"], scenario=SCENARIO_GUIDE[scenario],
        difficulty=difficulty, level_help=LEVEL_HELP[level_of(difficulty)], length=LENGTH_GUIDE[difficulty],
        polite=POLITE_WAYS.get(language, POLITE_WAYS["en"]), passages=unit_passages(language, unit_id),
        recent="; ".join(list(recent)[-5:]) or "none")
    return ensure_language(call_model("Write the task now.", system, names).strip(), language, names), scenario


def assess(language, difficulty, task, answer, tries, history=(), spoken=None, names=()):
    """Feedback on one try. Returns {"reply", "passed", "finished"}."""
    level = level_of(difficulty)
    system = ASSESS_RULES.format(
        language=_language_name(language), difficulty=difficulty, level=level, task=task, tries=tries,
        max_tries=MAX_TRIES, hint_policy=HINT_POLICY[level], polite=POLITE_WAYS.get(language, POLITE_WAYS["en"]),
        spoken_rule=SPOKEN_RULE.format(measures=for_coach(spoken)) if spoken else "")
    lines = [f"{'Learner' if t['role'] == 'learner' else 'SOMA'}: {t['text']}" for t in list(history)[-6:]]
    lines.append(f"Learner: {answer.strip()}")
    reply = call_model("\n".join(lines), system, names)
    match = PASSED.search(reply)
    passed = bool(match) and match.group(1).lower() == "yes"
    feedback = ensure_language(PASSED.sub("", reply).strip(), language, names)
    return {"reply": feedback, "passed": passed, "finished": passed or tries >= MAX_TRIES}


def placement_unit(language, n):
    """Placement tasks come from different units, so the check covers more than one topic."""
    all_units = units(language)
    return all_units[(n * 2) % len(all_units)]["id"]


def start_difficulty(placement_passes):
    return START_AFTER_PLACEMENT[max(0, min(3, placement_passes))]


def random_unit(language):
    return random.choice(units(language))["id"]
