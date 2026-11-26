import os
import re
from functools import lru_cache

from dotenv import load_dotenv

from index import keyword_search, search

load_dotenv()

# Models are tried in this order; if one is busy or too slow, the next one is used
GEMINI_MODELS = [m.strip() for m in os.environ.get(
    "GEMINI_MODELS", "gemini-3.8-flash,gemini-3.7-flash,gemini-3.5-flash-lite").split(",") if m.strip()]
GEMINI_TIMEOUT_MS = int(os.environ.get("GEMINI_TIMEOUT_MS", "15000"))
last_model_used = None

# Retrieval settings
TOP_K = 5
KEYWORD_K = 8           # keyword candidates scored by meaning
KEYWORD_ALWAYS = 3      # the best keyword matches are always passed on, even with a lower score
MAX_PASSAGES = 7
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
- The passages may be in another language than the question, or use other words for the
  same idea (for example "speaking politely" and "courteous communication"). If a passage
  explains the idea asked about, answer from it, explained in the learner's language.
- Answer only if a passage really answers this exact question. A passage that only shares a word
  or a topic with the question is not enough. If no passage answers it, reply with exactly: {NOT_IN_BOOK_TOKEN}
- Questions about beliefs, religion or politics are answered only if a passage answers them; otherwise {NOT_IN_BOOK_TOKEN}.
- After each fact, cite its source in brackets, copying the label exactly as given,
  e.g. (GSCS S4, p. 48) or (English S4, PDF p. 9).
- Write the WHOLE answer in the language requested, even when the passages are in another language:
  translate what you use. Kinyarwanda (Ikinyarwanda) and Kiswahili are different languages.
- Use simple, clear sentences suitable for the learner's age.
- Keep the answer short: at most about 120 words. Do not start with a greeting.
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

    # No hidden retries: if a model is busy, SOMA moves straight to the next one
    return genai.Client(
        api_key=os.environ["GEMINI_API_KEY"],
        http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_MS,
                                       retry_options=types.HttpRetryOptions(attempts=1)),
    )


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


def transcribe(audio, language="en", mime_type="audio/wav", context=""):
    """Write down what a learner said, exactly as said (hesitations kept, mistakes not corrected).

    The recording is sent to the model once and never stored. The transcript then goes
    through call_model like any typed answer, so personal details are removed there.
    """
    from google.genai import types

    name = LANGUAGE_NAMES.get(language, "English")
    prompt = (f"Transcribe this recording of a learner speaking {name}. Write exactly what was said, "
              f"in {name}, including hesitations (eh, umm) and repeated words. Do not correct mistakes, "
              "do not translate and do not add anything. If nothing is said, reply with nothing.")
    if context:
        prompt += (f"\nThe learner was answering this task, which may help you recognise the words: {context[:600]}\n"
                   "Use it only to recognise words; never add words that were not said.")
    return _gemini([prompt, types.Part.from_bytes(data=audio, mime_type=mime_type)], "")


# --- Answering in the learner's language ---

NATIVE_NAMES = {"en": "English", "rw": "Ikinyarwanda", "sw": "Kiswahili", "fr": "français"}

# Common little words that appear in almost every sentence of one language and rarely in the others
LANGUAGE_WORDS = {
    "rw": {"kandi", "cyangwa", "ariko", "kugira", "ngo", "ibi", "ibyo", "icyo", "iki", "uko", "nta", "ntabwo", "kuko",
           "nuko", "bityo", "cyane", "uyu", "abo", "uwo", "ari", "kuri", "kubera", "rero", "ndetse", "maze", "nyuma",
           "mbere", "buri", "byose", "bose", "hari", "umuntu", "abantu", "ubwo", "aho", "bikaba", "ese", "nk", "iyi"},
    "sw": {"kwa", "katika", "hiyo", "huu", "hii", "hilo", "sana", "kama", "lakini", "pia", "yake", "zake", "wake",
           "wao", "yeye", "kuwa", "kwamba", "hivyo", "ili", "au", "mtu", "watu", "kila", "bado", "sasa", "zaidi",
           "hakuna", "ambayo", "ambao", "ambaye", "hapa", "tena", "mahali", "mungu", "mzee", "huyo", "vya", "cha"},
    "en": {"the", "and", "is", "are", "of", "to", "that", "it", "with", "for", "this", "you", "not", "they", "be"},
    "fr": {"le", "la", "les", "et", "est", "des", "une", "un", "que", "qui", "dans", "pour", "pas", "ce", "il",
           "elle", "vous", "avec", "sur", "au", "du"},
}


def detect_language(text):
    """Best guess of the text's language from its little words, or None when unsure."""
    words = re.findall(r"[a-zà-ÿ]+", re.sub(r"\([^)]*\)", " ", text.lower()))   # citations do not count
    scores = {lang: sum(1 for w in words if w in vocab) for lang, vocab in LANGUAGE_WORDS.items()}
    best, second = sorted(scores.values(), reverse=True)[:2]
    if best < 2 or best < 1.5 * second:
        return None
    return max(scores, key=scores.get)


def ensure_language(text, language, names=()):
    """If a reply came back in another language, rewrite it in the learner's language."""
    found = detect_language(text)
    if found is None or found == language:
        return text
    prompt = (f"Rewrite this text in {LANGUAGE_NAMES.get(language, 'English')} ({NATIVE_NAMES.get(language)}). "
              "Keep the meaning. Keep everything in brackets, such as page citations, exactly as it is. "
              f"Reply with the rewritten text only.\n\n{text}")
    rewritten = call_model(prompt, names=names).strip()
    return rewritten or text


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
        found, keyword_ids = {}, []

        def keep(results):
            for result in results:
                if result["id"] not in found or result["score"] > found[result["id"]]["score"]:
                    found[result["id"]] = result

        for query in queries:
            keep(search(query, k=TOP_K, source_types=source_types))
            keywords = keyword_search(query, k=KEYWORD_K, source_types=source_types)
            keep(keywords)
            keyword_ids += [r["id"] for r in keywords[:KEYWORD_ALWAYS]]
        if language != "en":
            # Also search the books written in the learner's language, so a Kinyarwanda
            # question about a Kinyarwanda topic is not matched to similar-looking Kiswahili pages
            keep(search(question, k=TOP_K, source_types=source_types, language=language))

        ranked = sorted(found.values(), key=lambda r: r["score"], reverse=True)
        # The best keyword matches get their places first, so the passage limit
        # cuts the weakest meaning matches instead of a page with the exact words
        chosen = [found[chunk_id] for chunk_id in dict.fromkeys(keyword_ids)]
        chosen += [r for r in ranked[:TOP_K] if r["id"] not in set(keyword_ids)]
        return chosen[:MAX_PASSAGES]

    results = best_of(["reb"])
    if not results or results[0]["score"] < REB_GOOD_SCORE:
        results = results + [r for r in best_of(["extra"])[:2] if r["id"] not in {c["id"] for c in results}]
    results.sort(key=lambda r: r["score"], reverse=True)
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
    # "retrieved" lists the pages SOMA looked at, even when it refuses
    result = {"question": question, "language": language, "translated": translated,
              "best_score": best, "retrieved": [citation(p) for p in passages],
              "sources": [], "grounded": False}

    if best < MIN_SCORE:
        result["answer"] = NOT_IN_BOOK[language]
        return result

    context = "\n\n".join(f"[{citation(p)}]\n{p['text']}" for p in passages)
    prompt = (f"Passages:\n{context}\n\n"
              f"Learner's question: {question}\n"
              f"Answer in {LANGUAGE_NAMES.get(language, 'English')} ({NATIVE_NAMES.get(language, 'English')}) only.")
    reply = call_model(prompt, SYSTEM_RULES, names)
    if reply and NOT_IN_BOOK_TOKEN not in reply:
        reply = ensure_language(reply, language, names)

    if not reply or NOT_IN_BOOK_TOKEN in reply:
        result["answer"] = NOT_IN_BOOK[language]
        return result

    result.update(answer=reply, grounded=True,
                  sources=[{"citation": citation(p), "score": p["score"]} for p in passages])
    return result
