import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "soma"))

import index  # noqa: E402

CHUNKS = [
    {"id": "student-en", "audience": "student", "source_type": "reb", "language": "en", "text": "a"},
    {"id": "teacher-en", "audience": "teacher", "source_type": "reb", "language": "en", "text": "b"},
    {"id": "student-rw", "audience": "student", "source_type": "reb", "language": "rw", "text": "c"},
    {"id": "extra-en", "audience": "student", "source_type": "extra", "language": "en", "text": "d"},
]


def fake_index(monkeypatch, best_id):
    """All chunks get a low score except best_id, which matches the question perfectly."""
    vectors = np.array([[1.0, 0.0] if c["id"] == best_id else [0.0, 1.0] for c in CHUNKS], dtype=np.float32)
    monkeypatch.setattr(index, "load_index", lambda model_key: (CHUNKS, vectors))
    monkeypatch.setattr(index, "embed", lambda texts, model_key, kind: np.array([[1.0, 0.0]], dtype=np.float32))


def test_students_never_get_teacher_guides(monkeypatch):
    fake_index(monkeypatch, best_id="teacher-en")
    ids = [r["id"] for r in index.search("question", k=4)]
    assert "teacher-en" not in ids


def test_teachers_can_search_everything(monkeypatch):
    fake_index(monkeypatch, best_id="teacher-en")
    assert index.search("question", k=1, audience=None)[0]["id"] == "teacher-en"


def test_language_and_source_filters(monkeypatch):
    fake_index(monkeypatch, best_id="student-en")
    assert {r["language"] for r in index.search("q", k=4, language="rw")} == {"rw"}
    assert {r["source_type"] for r in index.search("q", k=4, source_types=["extra"])} == {"extra"}


def test_results_are_sorted_best_first(monkeypatch):
    fake_index(monkeypatch, best_id="student-rw")
    results = index.search("question", k=3)
    assert results[0]["id"] == "student-rw"
    assert [r["score"] for r in results] == sorted([r["score"] for r in results], reverse=True)