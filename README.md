# SOMA · Vuga Wiyizeye

A speaking coach that helps Senior 4 learners in Rwanda speak fluently, clearly and politely in Kinyarwanda, English, Kiswahili and French. Practice and answers are grounded in REB textbooks, with page citations.

Built for the Digital Umuganda & IndabaX Cameroon AI for Education fellowship. See [use_case.md](use_case.md), [workplan.md](workplan.md) and [docs/learning_sequence.md](docs/learning_sequence.md).

## Try SOMA

**1. Live (nothing to install):** [stephyrukundokeza--soma-web.modal.run](https://stephyrukundokeza--soma-web.modal.run)
Demo teacher and learner accounts are in my application. The first visit after a quiet period takes about a minute while SOMA wakes up. Use a phone to try the microphone.

**2. Watch:** a short video walkthrough (link to be added).

**3. Run it on your computer (about 10 minutes):** see [Run locally](#run-locally).

## What SOMA does
- **Practice:** a placement check sets Level 1, 2 or 3 in each language. Tasks (debate, interview, presentation) are created from the book unit for each learner, never written in advance. Learners answer by speaking or writing; hints come before answers.
- **Fluency measures:** speed against each language's own range, pauses, fillers and the polite phrases taught, shown after every spoken answer.
- **Levels:** Level 1 is guided, Level 2 gives partial help, Level 3 is free speaking. Two greens in a row move up; two yellows give more help.
- **Ask SOMA:** questions answered only from the books, with the page, or "This is not in your book."
- **Reading:** a table of contents per language and a clean reading view.
- **Teachers:** classes with a join code, timed sessions (40 minutes in class, 4 for a demo), and a dashboard with each learner's starting level and daily progress.

## How it works
1. **Extract** (`extract.py`): reads each PDF page, with OCR for scanned pages; tables kept as Markdown.
2. **Chunk** (`chunk.py`): splits pages into labelled pieces (book, language, unit, page, skill).
3. **Index** (`index.py`): hybrid search, by meaning (`multilingual-e5-base`) and by rare keywords.
4. **Answer** (`rag.py`): Gemini answers only from the retrieved passages and cites the page; replies in the wrong language are rewritten in the learner's language.
5. **Speak** (`speech.py`): [Digital Umuganda's Kinyarwanda Whisper model](https://huggingface.co/DigitalUmuganda/whisper_small_kinyarwanda) for Kinyarwanda, Gemini for English, Kiswahili and French. Recordings are never stored.
6. **Measure** (`fluency.py`): counted by SOMA, not guessed by a model.
7. **Adapt** (`practice.py`, `tutor.py`): generated tasks, levels and the guided skill "disagreeing politely".
8. **Track** (`accounts.py`, `etl.py`): Supabase accounts with admin, teacher and learner roles; an ETL pipeline turns practice events into daily totals (watermark, idempotent upserts, backfill). Only numbers are stored, never answers or recordings.

Teacher's guides are hidden from learners. Names, phone numbers and emails are removed before any text reaches a model.

## Results
- **Documents:** 14 documents, 2,860 pages, 786 tables, 3,871 chunks.
- **Search model:** `multilingual-e5-base` found the right page first where LaBSE missed it, so I chose e5.
- **Answers:** on a 30-question test set (English, Kinyarwanda, Kiswahili), the right page is found for 28 of 28 questions and cited in 27 of 28 answers, and both off-topic questions are refused. Adding keyword search to meaning search raised the score from 19 to 27. Kinyarwanda questions about English-only content are answered in Kinyarwanda.
- **Speed:** with the fastest Gemini model tried first, answers on the live site arrive in about 2 seconds.

## Run locally
Requires Python 3.11+, a free [Supabase](https://supabase.com) project and a [Gemini API key](https://aistudio.google.com/apikey).

```bash
python -m venv .venv
.venv\Scripts\activate              # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env              # add your Gemini and Supabase keys
```

1. In Supabase, open **SQL Editor**, paste [supabase/setup.sql](supabase/setup.sql) and run it.
2. Put the ready-made index (`chunks.json`, `embeddings_e5.npy`, `index_info_e5.json`) in `data/processed/`. It is shared privately with reviewers, because it contains REB book text. You can also [rebuild it from the books](#rebuild-the-index-from-the-books).
3. Create accounts (passwords are typed in privately), then start SOMA:

```bash
python scripts/add_user.py teacher mwarimu "Mwarimu"
python scripts/add_user.py learner umunyeshuri "Umunyeshuri"
python app.py                       # open http://127.0.0.1:8000
python -m pytest -q                 # the tests also run without the books
```

Optional: `python scripts/download_speech_model.py` downloads the Kinyarwanda speech model (about 1 GB) to run on your computer; without it, Gemini transcribes Kinyarwanda.

## Deploy
SOMA runs on [Modal](https://modal.com) with both models built in: `pip install modal`, `modal setup`, then `modal deploy modal_app.py`. Keys are copied from `.env` into a Modal secret; the index is copied into the private image.

## Rebuild the index from the books
Requires [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) (with French and Swahili). Download the REB textbooks listed in [use_case.md](use_case.md) from [elearning.reb.rw](https://elearning.reb.rw) into `data/raw/`, then:

```bash
python src/soma/extract.py
python src/soma/chunk.py
python src/soma/index.py build
python scripts/evaluate.py --name check     # the 30-question test set
```

## Technical notes
- PyMuPDF is pinned to 1.28.2, because table detection in 2.x crashes on Windows.
- Part of the GSCS PDF uses a broken font; `chunk.py` repairs the text automatically.
- If a Gemini model is overloaded, SOMA switches to the next model in `GEMINI_MODELS`.

## Licence
© 2026 Stephy Rukundo Keza. All rights reserved.
REB textbooks belong to the Government of Rwanda and are not included.
Kinyarwanda speech recognition uses [whisper_small_kinyarwanda](https://huggingface.co/DigitalUmuganda/whisper_small_kinyarwanda) by **Digital Umuganda**, a fine-tuned version of OpenAI's Whisper. Its model page does not state a licence, so I will confirm permission with Digital Umuganda before any school pilot.
Uses *Communication in Practice* by Jeremy Rose (University of Minnesota Libraries Publishing, 2025), CC BY 4.0.
