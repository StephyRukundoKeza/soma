import json
import os
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np

PROCESSED = Path("data/processed")
CHUNKS_FILE = PROCESSED / "chunks.json"
BATCH_SIZE = 32

# name -> (Hugging Face model, prefix for questions, prefix for passages)
MODELS = {
    "labse": ("sentence-transformers/LaBSE", "", ""),
    "e5": ("intfloat/multilingual-e5-base", "query: ", "passage: "),
}
DEFAULT_MODEL = os.environ.get("SOMA_EMBED_MODEL", "e5")

# Questions used by "compare": (question, source and printed page of the expected answer)
COMPARE_QUESTIONS = [
    ("What are the barriers to effective communication?", "gscs_s4", 48),
    ("Ni izihe mbogamizi zibangamira itumanaho ryiza?", "gscs_s4", 48),
    ("Who won the 2026 football World Cup?", None, None),
]


def files_for(model_key):
    """Each model keeps its own index, so you can switch without rebuilding."""
    return PROCESSED / f"embeddings_{model_key}.npy", PROCESSED / f"index_info_{model_key}.json"


@lru_cache(maxsize=2)
def get_model(model_key):
    """Load an embedding model once (downloaded on first use)."""
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODELS[model_key][0])


def embed(texts, model_key, kind, show_progress=False):
    """Turn texts into normalised vectors. kind is "query" or "passage"."""
    _, query_prefix, passage_prefix = MODELS[model_key]
    prefix = query_prefix if kind == "query" else passage_prefix
    vectors = get_model(model_key).encode(
        [prefix + text for text in texts],
        batch_size=BATCH_SIZE,
        normalize_embeddings=True,
        show_progress_bar=show_progress,
        convert_to_numpy=True,
    )
    return np.asarray(vectors, dtype=np.float32)


def build(model_key):
    """Embed every chunk with one model and save the vectors."""
    chunks = json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))
    embeddings_file, info_file = files_for(model_key)
    print(f"Embedding {len(chunks)} chunks with {MODELS[model_key][0]}...")
    vectors = embed([chunk["text"] for chunk in chunks], model_key, "passage", show_progress=True)
    np.save(embeddings_file, vectors)
    info = {"model": MODELS[model_key][0], "chunks": len(chunks), "dimensions": int(vectors.shape[1])}
    info_file.write_text(json.dumps(info, indent=1), encoding="utf-8")
    print(f"Saved {vectors.shape[0]} vectors of {vectors.shape[1]} numbers -> {embeddings_file}")


@lru_cache(maxsize=2)
def load_index(model_key):
    """Load the chunks and one model's vectors once."""
    embeddings_file, _ = files_for(model_key)
    if not embeddings_file.exists():
        raise FileNotFoundError(f"No {model_key} index yet. Run: python src/soma/index.py build --model {model_key}")
    chunks = json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))
    vectors = np.load(embeddings_file)
    if len(chunks) != len(vectors):
        raise RuntimeError(f"chunks.json and {embeddings_file.name} do not match. "
                           f"Run: python src/soma/index.py build --model {model_key}")
    return chunks, vectors


def search(question, k=5, audience="student", source_types=None, language=None, model_key=None):
    """Return the k chunks closest in meaning to the question, best first.

    audience="student" leaves out teacher-only material (teacher's guides and
    guidance documents); use audience=None to search everything.
    source_types limits the search, e.g. ["reb"] or ["extra"].
    language limits the search to one language code, e.g. "rw".
    """
    model_key = model_key or DEFAULT_MODEL
    chunks, vectors = load_index(model_key)
    scores = vectors @ embed([question], model_key, "query")[0]

    allowed = np.array([
        (audience is None or chunk["audience"] == audience)
        and (source_types is None or chunk["source_type"] in source_types)
        and (language is None or chunk["language"] == language)
        for chunk in chunks
    ])
    scores = np.where(allowed, scores, -1.0)

    best = np.argsort(-scores)[:k]
    return [{**chunks[i], "score": round(float(scores[i]), 3)} for i in best if allowed[i]]


def print_results(results):
    for result in results:
        page = result["printed_page"] or result["page"]
        print(f"{result['score']:.3f}  {result['source']} p.{page}  [{result['unit']}]")
        print(f"       {result['text'][:150]}...")


def compare():
    """Run the same questions on every model that has an index."""
    for model_key in MODELS:
        if not files_for(model_key)[0].exists():
            print(f"\n=== {model_key}: no index yet (build it first)")
            continue
        print(f"\n=== {model_key}")
        for question, source, page in COMPARE_QUESTIONS:
            results = search(question, model_key=model_key)
            rank = next((n + 1 for n, r in enumerate(results)
                         if source and r["source"] == source and (r["printed_page"] or r["page"]) == page), None)
            expected = f"expected {source} p.{page}: " + (f"rank {rank}" if rank else "not in top 5") if source \
                else "not in the books"
            print(f"  best {results[0]['score']:.3f} | {expected} | {question}")


def main():
    args = sys.argv[1:]
    model_key = DEFAULT_MODEL
    if "--model" in args:
        position = args.index("--model")
        model_key = args[position + 1]
        del args[position:position + 2]
    if model_key not in MODELS:
        print(f"Unknown model '{model_key}'. Choose from: {', '.join(MODELS)}")
        return

    if args[:1] == ["build"]:
        build(model_key)
    elif args[:1] == ["search"] and len(args) >= 2:
        print_results(search(" ".join(args[1:]), model_key=model_key))
    elif args[:1] == ["compare"]:
        compare()
    else:
        print("Usage: python src/soma/index.py build [--model e5|labse]")
        print('       python src/soma/index.py search "your question" [--model e5|labse]')
        print("       python src/soma/index.py compare")


if __name__ == "__main__":
    main()