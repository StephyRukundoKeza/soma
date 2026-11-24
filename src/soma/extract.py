import json
import sys
from pathlib import Path

import pymupdf
import pytesseract
from PIL import Image

RAW = Path("data/raw")
OUT = Path("data/processed")

# Tesseract language for each book; any book not listed uses English
OCR_LANG = {
    "french_s4": "fra",
    "french_s4_tg": "fra",
    "kiswahili_s4": "swa",
    "kiswahili_s4_tg": "swa",
}

# A page with less text than this is treated as scanned
MIN_CHARS = 20


def ocr_page(page, lang):
    """Read the text of a scanned page by turning it into an image."""
    pix = page.get_pixmap(dpi=300)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    return pytesseract.image_to_string(img, lang=lang)


def get_tables(page):
    """Return every table on the page as Markdown text."""
    try:
        return [table.to_markdown() for table in page.find_tables().tables]
    except Exception:
        return []


def extract_book(pdf_path):
    """Return one record per page: its text, how it was read, and its tables."""
    lang = OCR_LANG.get(pdf_path.stem, "eng")
    pages = []
    with pymupdf.open(pdf_path) as doc:
        for i, page in enumerate(doc):
            text = page.get_text()
            method = "text"
            if len(text.strip()) < MIN_CHARS:
                try:
                    text = ocr_page(page, lang)
                    method = "ocr"
                except pytesseract.TesseractError as err:
                    print(f"  OCR failed on page {i + 1}: {err}")
                    method = "failed"
            pages.append({
                "source": pdf_path.stem,
                "page": i + 1,
                "method": method,
                "text": text.strip(),
                "tables": get_tables(page),
            })
            if (i + 1) % 25 == 0:
                print(f"  {pdf_path.stem}: {i + 1}/{len(doc)} pages")
    return pages


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    names = sys.argv[1:] or sorted(p.stem for p in RAW.glob("*.pdf"))
    for name in names:
        pdf_path = RAW / f"{name}.pdf"
        if not pdf_path.exists():
            print(f"Not found: {pdf_path}")
            continue
        print(f"Extracting {name}...")
        pages = extract_book(pdf_path)
        out_path = OUT / f"{name}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(pages, f, ensure_ascii=False, indent=1)
        n_ocr = sum(p["method"] == "ocr" for p in pages)
        n_tables = sum(len(p["tables"]) for p in pages)
        print(f"{name}: {len(pages)} pages, {n_ocr} OCR, {n_tables} tables -> {out_path}")


if __name__ == "__main__":
    main()