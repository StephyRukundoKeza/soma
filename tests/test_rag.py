import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "soma"))

import rag  # noqa: E402


def fake_chunk(score, source="gscs_s4", page=48, chunk_id="c1"):
    return {"id": chunk_id, "source": source, "page": page + 8, "printed_page": page,
            "text": "Barriers to communication include noise and language.", "score": score}


def test_personal_info_is_removed():
    text = "My name is Aline, call me on 0788 123 456 or aline@mail.com"
    cleaned = rag.remove_personal_info(text, names=["Aline"])
    assert "Aline" not in cleaned and "0788" not in cleaned and "@" not in cleaned


def test_model_never_receives_personal_info(monkeypatch):
    sent = {}
    monkeypatch.setattr(rag, "_gemini", lambda prompt, system: sent.setdefault("prompt", prompt))
    rag.call_model("I am Aline, 0788123456", names=["Aline"])
    assert "Aline" not in sent["prompt"] and "0788123456" not in sent["prompt"]


def test_off_topic_question_does_not_call_the_model(monkeypatch):
    monkeypatch.setattr(rag, "search", lambda *a, **k: [fake_chunk(0.50)])
    calls = []
    monkeypatch.setattr(rag, "_gemini", lambda *a: calls.append(a) or "should not be used")
    result = rag.answer("Who won the World Cup?")
    assert result["answer"] == rag.NOT_IN_BOOK["en"] and not calls


def test_model_can_say_not_in_book_in_the_learners_language(monkeypatch):
    monkeypatch.setattr(rag, "search", lambda *a, **k: [fake_chunk(0.90)])
    monkeypatch.setattr(rag, "_gemini", lambda prompt, system: rag.NOT_IN_BOOK_TOKEN)
    result = rag.answer("Ikibazo", language="rw")
    assert result["answer"] == rag.NOT_IN_BOOK["rw"] and not result["grounded"]


def test_grounded_answer_has_page_citations(monkeypatch):
    monkeypatch.setattr(rag, "search", lambda *a, **k: [fake_chunk(0.90)])
    monkeypatch.setattr(rag, "_gemini", lambda prompt, system: "Noise is a barrier (GSCS S4, p. 48).")
    result = rag.answer("What are the barriers to communication?")
    assert result["grounded"] and result["sources"][0]["citation"] == "GSCS S4, p. 48"


def test_non_english_question_is_also_searched_in_english(monkeypatch):
    queries = []
    monkeypatch.setattr(rag, "search", lambda q, **k: queries.append(q) or [fake_chunk(0.90)])
    monkeypatch.setattr(rag, "_gemini", lambda prompt, system: "barriers to communication"
                        if "Translate" in prompt else "Answer (GSCS S4, p. 48)")
    rag.answer("Ni izihe mbogamizi?", language="rw")
    assert "barriers to communication" in queries



class FakeModels:
    def __init__(self, busy):
        self.busy, self.tried = busy, []

    def generate_content(self, model, contents, config):
        self.tried.append(model)
        if model in self.busy:
            raise RuntimeError("503 UNAVAILABLE")
        return type("Reply", (), {"text": f"answer from {model}"})()


def test_busy_model_falls_back_to_the_next(monkeypatch):
    models = FakeModels(busy={"model-a"})
    monkeypatch.setattr(rag, "GEMINI_MODELS", ["model-a", "model-b"])
    monkeypatch.setattr(rag, "get_client", lambda: type("Client", (), {"models": models})())
    assert rag.call_model("hello") == "answer from model-b"
    assert models.tried == ["model-a", "model-b"] and rag.last_model_used == "model-b"


def test_all_models_busy_raises_a_clear_error(monkeypatch):
    models = FakeModels(busy={"model-a", "model-b"})
    monkeypatch.setattr(rag, "GEMINI_MODELS", ["model-a", "model-b"])
    monkeypatch.setattr(rag, "get_client", lambda: type("Client", (), {"models": models})())
    try:
        rag.call_model("hello")
        assert False, "expected ModelsBusyError"
    except rag.ModelsBusyError as error:
        assert "model-a" in str(error) and "model-b" in str(error)