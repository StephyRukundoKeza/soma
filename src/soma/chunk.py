import json
import re
from collections import Counter
from pathlib import Path

PROCESSED = Path("data/processed")
OUT_FILE = PROCESSED / "chunks.json"

CHUNK_WORDS = 350
OVERLAP_WORDS = 50
MIN_WORDS = 25

# source name -> (subject, language, source_type, audience)
SOURCES = {
    "gscs_s4": ("GSCS", "en", "reb", "student"),
    "gscs_s4_tg": ("GSCS", "en", "reb", "teacher"),
    "english_s4": ("English", "en", "reb", "student"),
    "english_s4_tg": ("English", "en", "reb", "teacher"),
    "kinyarwanda_s4": ("Ikinyarwanda", "rw", "reb", "student"),
    "kinyarwanda_s4_tg": ("Ikinyarwanda", "rw", "reb", "teacher"),
    "kiswahili_s4": ("Kiswahili", "sw", "reb", "student"),
    "kiswahili_s4_tg": ("Kiswahili", "sw", "reb", "teacher"),
    "french_s4": ("Francais", "fr", "reb", "student"),
    "french_s4_tg": ("Francais", "fr", "reb", "teacher"),
    "guidance_counselling_module1": ("Guidance and Counselling", "en", "guidance", "teacher"),
    "career_pathways_report": ("Career Pathways", "en", "guidance", "teacher"),
    "career_guidance_tg": ("Career Guidance", "en", "guidance", "teacher"),
    "comm_practice": ("Communication", "en", "extra", "student"),
}

# Unit headings in each book's style. A number (or a Kinyarwanda ordinal) is required.
HEADING_PATTERNS = [
    re.compile(r"^(?:UNIT|Unit)\s+(\d+)\b\s*[:.\-]?\s*(.*)$"),
    re.compile(r"^(?:UNIT[EÉ]|Unit[eé])\s+(\d+)\s*[:.]?\s*(.*)$"),
    re.compile(r"^(?:CHAPTER|Chapter)\s+([IVX]+|\d+)\s*:\s*(.*)$"),
    re.compile(r"^MADA KUU YA\s+(\d+)\s*:?\s*(.*)$", re.IGNORECASE),
    re.compile(r"^UMUTWE(?:\s+WA)?\s+(\d+[AB]?)\b\s*:?\s*(.*)$"),
    re.compile(r"^(?:Umutwe|UMUTWE) (?:wa|WA)\s+(mbere|kabiri|gatatu|kane|gatanu|gatandatu|karindwi|"
               r"munani|kenda|cumi|\d+)\b\s*:?\s*(.*)$", re.IGNORECASE),
]

SKILL_WORDS = {
    "speaking": ["speaking", "oral work", "debate", "discussion", "presentation", "public speaking",
                 "kuzungumza", "mazungumzo", "mjadala", "midahalo", "expression orale",
                 "kuvuga", "ikiganiro", "impaka"],
    "listening": ["listening", "listen to", "kusikiliza", "écoute", "compréhension orale",
                  "gutega amatwi"],
    "reading": ["reading", "read the text", "read the passage", "kusoma", "lecture",
                "gusoma", "umwandiko"],
    "writing": ["writing", "write a", "kuandika", "insha", "rédaction", "production écrite",
                "kwandika", "ihimbamwandiko"],
    "grammar": ["grammar", "language structure", "sarufi", "grammaire", "conjugaison",
                "ikibonezamvugo", "ntera"],
}

TOC_LINE = re.compile(r"(\.\s*){3,}\s*\d*\s*$|\s\d+\s*$")

# Some REB PDFs store text with a broken font: every character is shifted
# down by 29 (so "the" appears as "WKH" and a space as "\x03").
FONT_SHIFT = 29
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def repair_text(text):
    """Undo the font shift in words that contain control characters."""
    if not CONTROL_CHARS.search(text):
        return text
    parts = re.split(r"([ \t\n]+)", text)
    for i, word in enumerate(parts):
        if CONTROL_CHARS.search(word):
            parts[i] = "".join(chr(ord(c) + FONT_SHIFT) if ord(c) + FONT_SHIFT < 127 else c
                               for c in word)
    return "".join(parts)


def find_headings(text):
    """Return the unit headings on a page, skipping table-of-contents lines."""
    lines = [" ".join(line.split()) for line in text.splitlines()]
    lines = [line for line in lines if line]
    found = []
    for i, line in enumerate(lines):
        # Style used by GSCS and others: title line(s), then "Unit", then the number
        if line in ("Unit", "UNIT") and i + 1 < len(lines) and lines[i + 1].isdigit():
            title_lines = []
            for prev in reversed(lines[:i]):
                if prev.isdigit():
                    break
                title_lines.insert(0, prev)
            title = " ".join(title_lines[-2:])
            found.append((lines[i + 1], f"{lines[i + 1]}: {title}".strip(": ")))
            continue
        if TOC_LINE.search(line):
            continue
        for pattern in HEADING_PATTERNS:
            match = pattern.match(line)
            if match:
                number, title = match.group(1), match.group(2).strip(" :.-")
                found.append((number, f"{number}: {title}".strip(": ") if title else number))
                break
    return found


def printed_page(text):
    """Return the page number printed on the page, if the page starts with one."""
    for line in text.splitlines():
        line = line.strip()
        if line:
            return int(line) if line.isdigit() and len(line) <= 3 else None
    return None


def detect_skill(text):
    """Guess the main language skill a passage practises."""
    lowered = text.lower()
    scores = {skill: sum(lowered.count(w) for w in words) for skill, words in SKILL_WORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"


def split_words(text):
    """Cut text into overlapping pieces of about CHUNK_WORDS words."""
    words = text.split()
    step = CHUNK_WORDS - OVERLAP_WORDS
    pieces = []
    for start in range(0, len(words), step):
        piece = words[start:start + CHUNK_WORDS]
        if len(piece) >= MIN_WORDS:
            pieces.append(" ".join(piece))
        if start + CHUNK_WORDS >= len(words):
            break
    return pieces


def chunk_book(name, pages):
    subject, language, source_type, audience = SOURCES.get(name, (name, "en", "extra", "student"))
    current_unit = None
    chunks = []
    for page in pages:
        page["text"] = repair_text(page["text"])
        page["tables"] = [repair_text(t) for t in page["tables"]]
        if language != "fr":
            # A broken ligature turns "fi" into "À" in some English PDFs
            page["text"] = page["text"].replace("À", "fi")
            page["tables"] = [t.replace("À", "fi") for t in page["tables"]]
        headings = find_headings(page["text"])
        # A page listing three or more different units is a table of contents
        if headings and len({number for number, _ in headings}) < 3:
            current_unit = headings[-1][1]

        base = {
            "source": name,
            "subject": subject,
            "language": language,
            "source_type": source_type,
            "audience": audience,
            "unit": current_unit,
            "page": page["page"],
            "printed_page": printed_page(page["text"]),
            "method": page["method"],
        }
        for n, piece in enumerate(split_words(page["text"])):
            chunks.append({**base, "id": f"{name}-p{page['page']}-t{n}", "type": "text",
                           "skill": detect_skill(piece), "text": piece})
        for n, table in enumerate(page["tables"]):
            if len(table.split()) >= 10:
                chunks.append({**base, "id": f"{name}-p{page['page']}-tab{n}", "type": "table",
                               "skill": detect_skill(table), "text": table})
    return chunks


def main():
    all_chunks = []
    for path in sorted(PROCESSED.glob("*.json")):
        if path.name == OUT_FILE.name:
            continue
        pages = json.loads(path.read_text(encoding="utf-8"))
        chunks = chunk_book(path.stem, pages)
        all_chunks.extend(chunks)
        units = len({c["unit"] for c in chunks if c["unit"]})
        skills = Counter(c["skill"] for c in chunks)
        print(f"{path.stem}: {len(chunks)} chunks, {units} units, skills {dict(skills)}")
    OUT_FILE.write_text(json.dumps(all_chunks, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Total: {len(all_chunks)} chunks -> {OUT_FILE}")


if __name__ == "__main__":
    main()