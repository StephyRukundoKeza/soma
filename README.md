# SOMA

An AI tutor that helps Senior 4 learners in Rwanda communicate more fluently in Kinyarwanda, English, Kiswahili and French. Answers come only from REB textbooks, with page citations.

Built for the Digital Umuganda & IndabaX Cameroon AI for Education fellowship. See [use_case.md](use_case.md) and [workplan.md](workplan.md).

## How it works
1. **Extract** (`extract.py`): reads each PDF page, with OCR for scanned pages; tables kept as Markdown.
2. **Chunk** (`chunk.py`): splits pages into labelled pieces (book, language, unit, page, skill).
3. **Index** (`index.py`): searches by meaning with `multilingual-e5-base`.
4. **Answer** (`rag.py`): Gemini answers only from the retrieved passages and cites the page, or replies "This is not in your book."

Non-English questions are translated before searching. Teacher's guides are hidden from students. Names, phone numbers and emails are removed before any text reaches a model.

## Quick start
Requires Python 3.11+ and [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) (with French and Swahili).

```bash
python -m venv .venv
.venv\Scripts\activate              # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env              # then add your Gemini API key
```

Download the REB textbooks listed in [use_case.md](use_case.md) from [elearning.reb.rw](https://elearning.reb.rw) into `data/raw/`, then:

```bash
python src/soma/extract.py
python src/soma/chunk.py
python src/soma/index.py build
python scripts/ask.py "What are the barriers to effective communication?"
python scripts/ask.py "Ni izihe mbogamizi zibangamira itumanaho ryiza?" --lang rw
python -m pytest -q
```

## Results
- **Documents:** 14 documents, 2,860 pages, 786 tables, 3,871 chunks.
- **Search model:** `multilingual-e5-base` found the right page first where LaBSE missed it, so I chose e5.
- **Answers:** 6 of 6 test questions answered correctly with the right page, in English, Kinyarwanda and Kiswahili; the off-topic question was correctly refused. The Kinyarwanda answer had 2 spacing errors.

## Technical notes
- PyMuPDF is pinned to 1.28.2, because table detection in 2.x crashes on Windows.
- Part of the GSCS PDF uses a broken font; `chunk.py` repairs the text automatically.
- If a Gemini model is overloaded, SOMA switches to the next model in `GEMINI_MODELS`.

## Licence
© 2026 Stephy Rukundo Keza. All rights reserved.
REB textbooks belong to the Government of Rwanda and are not included. Uses *Communication in Practice* by Jeremy Rose (University of Minnesota Libraries Publishing, 2025), CC BY 4.0.
