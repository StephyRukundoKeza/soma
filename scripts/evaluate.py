import argparse
import csv
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src" / "soma"))

import rag  # noqa: E402

TEST_SET = ROOT / "evaluation" / "test_set.csv"
SCORE_COLUMNS = ["correctness_0_2", "grounding_0_2", "language_0_2", "clarity_0_2", "rater_notes"]


def normalise(text):
    """Compare citations without caring whether "PDF" is written before the page."""
    return re.sub(r"PDF\s+", "", text)


def run_question(row):
    """Ask SOMA one test question and check the answer against the expected source."""
    result, error = None, ""
    for attempt in range(2):
        start = time.time()
        try:
            result, error = rag.answer(row["question"], row["language"]), ""
            break
        except rag.ModelsBusyError as busy:
            error = str(busy)[:200]
            if "429" in error and attempt == 0:
                print("      free quota reached; waiting 30 s and trying again...")
                time.sleep(30)
    seconds = round(time.time() - start, 1)

    citations = result.get("retrieved", []) if result else []
    expected = [normalise(f"{row['source']}, {page.strip()}") for page in row["page"].split("|")] if row["source"] else []
    refused = bool(result) and result["answer"] == rag.NOT_IN_BOOK.get(row["language"])

    answer_text = result["answer"] if result else ""
    if row["type"] == "not_in_book":
        source_ok = page_ok = cited_ok = refused
    else:
        source_ok = any(c.startswith(row["source"]) for c in citations)
        found_pages = [normalise(c) for c in citations]
        page_ok = any(e in found_pages for e in expected)
        cited_ok = any(e in normalise(answer_text) for e in expected)

    return {
        **row,
        "answer": answer_text,
        "retrieved_pages": "; ".join(citations),
        "model": rag.last_model_used if result and result["grounded"] else "",
        "seconds": seconds,
        "best_score": round(result["best_score"], 3) if result else "",
        "book_retrieved": "yes" if source_ok else "no",
        "page_retrieved": "yes" if page_ok else "no",
        "page_cited_in_answer": "yes" if cited_ok else "no",
        "error": error,
        **{column: "" for column in SCORE_COLUMNS},
    }


def main():
    parser = argparse.ArgumentParser(description="Run the SOMA test set and save the results.")
    parser.add_argument("--model", help="use only this Gemini model (no fallback), for fair comparisons")
    parser.add_argument("--name", default="main", help="label for the results file")
    parser.add_argument("--limit", type=int, help="only run the first N questions")
    parser.add_argument("--ids", help="only run these question ids, e.g. 22,28,29,30")
    parser.add_argument("--pause", type=float, default=4.0, help="seconds to wait between questions")
    args = parser.parse_args()

    if args.model:
        rag.GEMINI_MODELS = [args.model]

    with open(TEST_SET, encoding="utf-8") as file:
        rows = list(csv.DictReader(file))[: args.limit]
    if args.ids:
        wanted = {i.strip() for i in args.ids.split(",")}
        rows = [row for row in rows if row["id"] in wanted]

    results = []
    for n, row in enumerate(rows, 1):
        result = run_question(row)
        results.append(result)
        print(f"{n:2}/{len(rows)}  {result['seconds']:5.1f}s  cited {result['page_cited_in_answer']:3}  "
              f"{result['model'] or '-':24}  {row['question'][:50]}")
        if n < len(rows):
            time.sleep(args.pause)

    out_file = ROOT / "evaluation" / f"results_{args.name}.csv"
    with open(out_file, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    answered = [r for r in results if not r["error"]]
    in_book = [r for r in results if r["type"] != "not_in_book"]
    not_in_book = [r for r in results if r["type"] == "not_in_book"]
    print(f"\nSaved {len(results)} results -> {out_file}")
    print(f"Answered without errors: {len(answered)}/{len(results)}")
    print(f"Right book retrieved:    {sum(r['book_retrieved'] == 'yes' for r in in_book)}/{len(in_book)}")
    print(f"Right page retrieved:    {sum(r['page_retrieved'] == 'yes' for r in in_book)}/{len(in_book)}")
    print(f"Right page in answer:    {sum(r['page_cited_in_answer'] == 'yes' for r in in_book)}/{len(in_book)}")
    print(f"Correct refusals:        {sum(r['page_cited_in_answer'] == 'yes' for r in not_in_book)}/{len(not_in_book)}")
    if answered:
        print(f"Average response time:   {sum(r['seconds'] for r in answered) / len(answered):.1f} s")
    models = sorted({r["model"] for r in results if r["model"]})
    print(f"Models that answered:    {', '.join(models) or '-'}")


if __name__ == "__main__":
    main()
