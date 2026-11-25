import os
import re
from functools import lru_cache

from dotenv import load_dotenv

from index import search

load_dotenv()

# Models are tried in this order; if one is busy or too slow, the next one is used
GEMINI_MODELS = [m.strip() for m in os.environ.get(
    "GEMINI_MODELS", "gemini-3.8-flash,gemini-3.7-flash,gemini-3.5-flash-lite").split(",") if m.strip()]
GEMINI_TIMEOUT_MS = int(os.environ.get("GEMINI_TIMEOUT_MS", "25000"))
last_model_used = None

# Retrieval settings
TOP_K = 5
MIN_SCORE = 0.78        # below this, nothing in the books is close enough
REB_GOOD_SCORE = 0.82   # below this, also look in the extra (non-REB) source

LANGUAGE_NAMES = {"en": "English", "rw": "Kinyarwanda", "sw": "Kiswahili", "fr": "French"}

NOT_IN_BOOK = {
    "en": "This is not in your book.",
    "rw": "Ibi ntibiri mu gitabo cyawe.",
    "sw": "Hili halipo kwenye kitabu chako.",
    "fr": "Ce n'est pas dans ton livre.",
}
NOT_IN_BOOK_TOKEN = "NOT_IN_BOOK"

SOURCE_LABELS = {
    "gscs_s4": "GSCS S4",
    "english_s4": "English S4",
    "kinyarwanda_s4": "Ikinyarwanda S4",
    "kiswahili_s4": "Kiswahili S4",
    "french_s4": "Français S4",
    "comm_practice": "Communication in Practice, outside the REB curriculum",
}

SYSTEM_RULES = f"""You are SOMA, a tutor for Senior 4 learners in Rwanda (about 15-17 years old).
Rules:
- Use ONLY the passages provided. Do not use outside knowledge.
- If the passages do not contain the answer, reply with exactly: {NOT_IN_BOOK_TOKEN}
- After each fact, cite its source in brackets exactly as labelled, e.g. (GSCS S4, p. 48).
- Answer in the language requested, in simple, clear sentences suitable for the learner's age.
- Keep the answer short: at most about 120 words.
- Never ask for or repeat personal information."""

# --- Privacy: every model call goes through call_model, which removes personal data first ---

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(?:\+?250[\s-]?)?0?7[2389][\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}\b|\+?\d[\d\s-]{8,}\d")


def remove_personal_info(text, names=()):
    """Replace emails, phone numbers and known student names before text leaves the app."""
    text = EMAIL.sub("[email]", text)
    text = PHONE.sub("[phone]", text)
    for name in names:
        if name:
            text = re.sub(rf"\b{re.escape(name)}\b", "[student]", text, flags=re.IGNORECASE)
    return text


class ModelsBusyError(RuntimeError):
    """Raised when every model in GEMINI_MODELS failed."""


@lru_cache(maxsize=1)
def get_client():
    from google import genai
    from google.genai import types

    return genai.Client(api_key=os.environ["GEMINI_API_KEY"],
                        http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_MS))


def _gemini(prompt, system):
    """Ask each model in turn until one answers."""
    from google.genai import types

    global last_model_used
    problems = []
    for model in GEMINI_MODELS:
        try:
            response = get_client().models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(system_instruction=system or None, temperature=0.2),
            )
            last_model_used = model
            return (response.text or "").strip()
        except Exception as error:
            problems.append(f"{model}: {str(error)[:80]}")
    raise ModelsBusyError("All models are busy or unavailable. " + " | ".join(problems))


def call_model(prompt, system="", names=()):
    """The only door to the language model."""
    return _gemini(remove_personal_info(prompt, names), system)


# --- Retrieval ---

def translate_to_english(question, language, names=()):
    """Translate a non-English question so the English-heavy index can find it."""
    if language == "en":
        return None
    prompt = (f"Translate this {LANGUAGE_NAMES.get(language, language)} question into English. "
              f"Reply with the translation only.\n\n{question}")
    return call_model(prompt, names=names)


def retrieve(question, language="en", names=()):
    """Find the best passages: REB books first, the extra source only if REB is weak."""
    queries = [question]
    translated = translate_to_english(question, language, names)
    if translated:
        queries.append(translated)

    def best_of(source_types):
        found = {}
        for query in queries:
            for result in search(query, k=TOP_K, source_types=source_types):
                if result["id"] not in found or result["score"] > found[result["id"]]["score"]:
                    found[result["id"]] = result
        return sorted(found.values(), key=lambda r: r["score"], reverse=True)[:TOP_K]

    results = best_of(["reb"])
    if not results or results[0]["score"] < REB_GOOD_SCORE:
        results = sorted(results + best_of(["extra"]), key=lambda r: r["score"], reverse=True)[:TOP_K]
    return results, translated


def citation(chunk):
    label = SOURCE_LABELS.get(chunk["source"], chunk["source"])
    page = f"p. {chunk['printed_page']}" if chunk.get("printed_page") else f"PDF p. {chunk['page']}"
    return f"{label}, {page}"


# --- Answering ---

def answer(question, language="en", names=()):
    """Answer a learner's question from the books only, with page citations."""
    passages, translated = retrieve(question, language, names)
    best = passages[0]["score"] if passages else 0.0
    result = {"question": question, "language": language, "translated": translated,
              "best_score": best, "sources": [], "grounded": False}

    if best < MIN_SCORE:
        result["answer"] = NOT_IN_BOOK[language]
        return result

    context = "\n\n".join(f"[{citation(p)}]\n{p['text']}" for p in passages)
    prompt = (f"Passages:\n{context}\n\n"
              f"Learner's question: {question}\n"
              f"Answer in {LANGUAGE_NAMES.get(language, 'English')}.")
    reply = call_model(prompt, SYSTEM_RULES, names)

    if not reply or NOT_IN_BOOK_TOKEN in reply:
        result["answer"] = NOT_IN_BOOK[language]
        return result

    result.update(answer=reply, grounded=True,
                  sources=[{"citation": citation(p), "score": p["score"]} for p in passages])
    return result