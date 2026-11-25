import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "soma"))

import rag  # noqa: E402


def main():
    args = sys.argv[1:]
    language = "en"
    if "--lang" in args:
        position = args.index("--lang")
        language = args[position + 1]
        del args[position:position + 2]
    if not args or language not in ("en", "rw", "sw", "fr"):
        print('Usage: python scripts/ask.py "your question" [--lang en|rw|sw|fr]')
        return

    try:
        result = rag.answer(" ".join(args), language)
    except rag.ModelsBusyError as error:
        print("SOMA could not reach a model right now. Please try again in a moment.")
        print(f"(details: {error})")
        return
    if result["translated"]:
        print(f"(searched in English as: {result['translated']})")
    print(f"\n{result['answer']}\n")
    print(f"Best match score: {result['best_score']:.3f}")
    if result["grounded"]:
        print(f"Answered by: {rag.last_model_used}")
    for source in result["sources"]:
        print(f"  - {source['citation']} (score {source['score']:.3f})")


if __name__ == "__main__":
    main()