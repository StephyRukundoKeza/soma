"""Table of contents and reading pages for each language, built from the S4 student books."""

import random
import re
from functools import lru_cache

from tutor import load_chunks

BOOKS = {"en": "english_s4", "rw": "kinyarwanda_s4", "sw": "kiswahili_s4", "fr": "french_s4"}
GRADE = "S4"            # the design is ready for S5 and S6: add their books here
OVERLAP_WORDS = 50      # chunks on the same page overlap by this many words (see chunk.py)


def _title(unit):
    """'3: L’HOMME INTEGRE' -> 'L’homme intègre'-style display text, keeping the book's words."""
    title = re.sub(r"^\w{1,3}:\s*", "", unit).strip()
    return title[:1].upper() + title[1:].lower() if title.isupper() else title


@lru_cache(maxsize=8)
def units(language):
    """[{"id", "number", "title", "first_page", "last_page"}] in book order."""
    source = BOOKS[language]
    found = []
    for chunk in load_chunks():
        if chunk["source"] != source or chunk["audience"] != "student" or not chunk.get("unit"):
            continue
        if found and found[-1]["unit"] == chunk["unit"]:
            found[-1]["last_page"] = max(found[-1]["last_page"], chunk["page"])
            continue
        found.append({"unit": chunk["unit"], "first_page": chunk["page"], "last_page": chunk["page"]})

    # A book printed in capitals marks its units in capitals; a short title in normal case
    # is a running header that continues the unit before it, so it is merged into that unit
    capitals = sum(u["unit"].split(":", 1)[-1].strip().isupper() for u in found) > len(found) / 2
    merged = []
    for unit in found:
        if merged and capitals and not unit["unit"].split(":", 1)[-1].strip().isupper():
            merged[-1]["last_page"] = unit["last_page"]
            merged[-1]["also"].append(unit["unit"])
        else:
            merged.append({**unit, "also": []})
    titles = [_title(u["unit"]) for u in merged]
    result = []
    for i, (unit, title) in enumerate(zip(merged, titles), 1):
        if titles.count(title) > 1:            # e.g. two parts 1A and 1B with the same title
            title = f"{title} ({unit['unit'].split(':')[0]})"
        result.append({"id": f"{language}-{i}", "number": i, "title": title, "first_page": unit["first_page"],
                       "last_page": unit["last_page"], "labels": [unit["unit"], *unit["also"]]})
    return result


def find_unit(language, unit_id):
    for unit in units(language):
        if unit["id"] == unit_id:
            return unit
    raise KeyError(unit_id)


def _unit_chunks(language, unit_id):
    unit = find_unit(language, unit_id)
    source = BOOKS[language]
    return [c for c in load_chunks()
            if c["source"] == source and c["audience"] == "student" and c.get("unit") in unit["labels"]
            and not c["text"].lstrip().startswith("|")]          # tables are already in the page text


@lru_cache(maxsize=8)
def running_header(language):
    """The words printed at the top of most pages (e.g. 'Ikinyarwanda Umwaka wa 4 ...'), to hide when reading."""
    from collections import Counter

    starts = Counter()
    for chunk in load_chunks():
        if chunk["source"] == BOOKS[language] and chunk["audience"] == "student":
            words = re.sub(r"^[\d\s]+", "", chunk["text"]).split()
            for n in range(4, 11):
                starts[" ".join(words[:n])] += 1
    pages = len({c["page"] for c in load_chunks() if c["source"] == BOOKS[language]})
    common = [(len(text), text) for text, count in starts.items() if count >= max(2, pages / 3)]
    return max(common)[1] if common else ""


def clean_page(text, language):
    text = re.sub(r"^[\d\s]+", "", text)                    # printed page number
    header = running_header(language)
    if header and text.startswith(header):
        text = text[len(header):].lstrip()
    return text


def unit_pages(language, unit_id):
    """The unit's text, page by page, for the reading view."""
    pages = {}
    for chunk in _unit_chunks(language, unit_id):
        words = chunk["text"].split()
        if chunk["page"] in pages:
            words = words[OVERLAP_WORDS:]              # skip the words repeated from the last chunk
        pages.setdefault(chunk["page"], {"page": chunk["page"], "printed_page": chunk.get("printed_page"),
                                         "text": ""})
        pages[chunk["page"]]["text"] += (" " if pages[chunk["page"]]["text"] else "") + " ".join(words)
    for page in pages.values():
        page["text"] = clean_page(page["text"], language)
    return [pages[p] for p in sorted(pages)]


def unit_passages(language, unit_id, count=2, chars=900, seed=None):
    """A few pages of the unit for the task generator, with labels to cite."""
    from rag import SOURCE_LABELS

    pages = unit_pages(language, unit_id)
    picked = random.Random(seed).sample(pages, min(count, len(pages)))
    label = SOURCE_LABELS.get(BOOKS[language], BOOKS[language])
    out = []
    for page in sorted(picked, key=lambda p: p["page"]):
        where = f"p. {page['printed_page']}" if page["printed_page"] else f"PDF p. {page['page']}"
        out.append(f"[{label}, {where}]\n{page['text'][:chars]}")
    return "\n\n".join(out)
