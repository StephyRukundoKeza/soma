import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "soma"))

import pytest  # noqa: E402

import rag  # noqa: E402


@pytest.fixture(autouse=True)
def no_keyword_search(monkeypatch):
    """Most tests fake search(); keyword search is switched off unless a test needs it."""
    monkeypatch.setattr(rag, "keyword_search", lambda *a, **k: [])


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


def test_non_english_question_also_searches_books_in_that_language(monkeypatch):
    languages = []
    monkeypatch.setattr(rag, "search", lambda q, **k: languages.append(k.get("language")) or [fake_chunk(0.90)])
    monkeypatch.setattr(rag, "_gemini", lambda prompt, system: "translated question"
                        if "Translate" in prompt else "Answer (Ikinyarwanda S4, p. 9)")
    rag.answer("Amavumvu ni iki?", language="rw")
    assert "rw" in languages


def test_english_question_does_not_add_a_language_filter(monkeypatch):
    languages = []
    monkeypatch.setattr(rag, "search", lambda q, **k: languages.append(k.get("language")) or [fake_chunk(0.90)])
    monkeypatch.setattr(rag, "_gemini", lambda prompt, system: "Answer (GSCS S4, p. 48)")
    rag.answer("What are the barriers?")
    assert set(languages) == {None}


def test_keyword_matches_are_added_to_the_results(monkeypatch):
    monkeypatch.setattr(rag, "search", lambda *a, **k: [fake_chunk(0.85, chunk_id="meaning")])
    monkeypatch.setattr(rag, "keyword_search",
                        lambda *a, **k: [fake_chunk(0.83, source="kinyarwanda_s4", page=9, chunk_id="keyword")])
    passages, _ = rag.retrieve("Amavumvu ni iki?")
    assert {p["id"] for p in passages} == {"meaning", "keyword"}


def test_top_keyword_match_is_kept_even_with_a_lower_score(monkeypatch):
    strong = [fake_chunk(0.90 - i / 100, chunk_id=f"meaning{i}") for i in range(5)]
    monkeypatch.setattr(rag, "search", lambda *a, **k: strong)
    monkeypatch.setattr(rag, "keyword_search",
                        lambda *a, **k: [fake_chunk(0.80, source="kinyarwanda_s4", page=9, chunk_id="bees")])
    passages, _ = rag.retrieve("Amavumvu ni iki?")
    assert "bees" in {p["id"] for p in passages} and len(passages) == 6


def test_keyword_matches_are_never_cut_by_the_passage_limit(monkeypatch):
    strong = [fake_chunk(0.90 - i / 100, source="kiswahili_s4", chunk_id=f"meaning{i}") for i in range(7)]
    monkeypatch.setattr(rag, "translate_to_english", lambda *a, **k: "When is the proverb used?")
    monkeypatch.setattr(rag, "search", lambda *a, **k: strong)
    by_query = {"Umugani bawuca ryari?": ["page12", "page15"], "When is the proverb used?": ["page12", "page11"]}
    monkeypatch.setattr(rag, "keyword_search", lambda question, **k: [
        fake_chunk(0.80, source="kinyarwanda_s4", chunk_id=c) for c in by_query[question]])
    passages, _ = rag.retrieve("Umugani bawuca ryari?", language="rw")
    ids = {p["id"] for p in passages}
    assert {"page11", "page12", "page15"} <= ids and len(passages) == rag.MAX_PASSAGES


def test_pages_looked_at_are_recorded_even_when_refusing(monkeypatch):
    monkeypatch.setattr(rag, "search", lambda *a, **k: [fake_chunk(0.85, page=12)])
    monkeypatch.setattr(rag, "call_model", lambda *a, **k: rag.NOT_IN_BOOK_TOKEN)
    result = rag.answer("What does it mean to listen well?")
    assert not result["grounded"] and result["sources"] == []
    assert result["retrieved"] == ["GSCS S4, p. 12"]


def test_language_of_a_reply_is_recognised():
    assert rag.detect_language("Mzee Kobe yalamikaye na kumsihi Mungu kulaza roho yake mahali pema (Kiswahili S4, PDF p. 224).") == "sw"
    assert rag.detect_language("Gutega amatwi ni ubushobozi bwo kumva neza kandi ntabwo ari ukumva gusa (GSCS S4, p. 12).") == "rw"
    assert rag.detect_language("Active listening is the ability to listen and not just hear.") == "en"
    assert rag.detect_language("Ok") is None


def test_a_reply_in_the_wrong_language_is_rewritten(monkeypatch):
    sent = {}
    monkeypatch.setattr(rag, "call_model", lambda prompt, system="", names=(): sent.setdefault("prompt", prompt) and "Igisubizo mu Kinyarwanda (Kiswahili S4, PDF p. 224)")
    text = "Mzee Kobe alimuomba Mungu kwa sababu yake na hapa (Kiswahili S4, PDF p. 224)."
    assert rag.ensure_language(text, "rw").startswith("Igisubizo")
    assert "Rewrite this text in Kinyarwanda (Ikinyarwanda)" in sent["prompt"]


def test_a_reply_in_the_right_language_is_kept(monkeypatch):
    monkeypatch.setattr(rag, "call_model", lambda *a, **k: "should not be called")
    text = "Gutega amatwi ni ubushobozi bwo kumva neza kandi ntabwo ari ukumva gusa."
    assert rag.ensure_language(text, "rw") == text


def test_rules_refuse_passages_that_only_share_a_word():
    assert "only shares a word" in rag.SYSTEM_RULES and "Kinyarwanda (Ikinyarwanda) and Kiswahili are different" in rag.SYSTEM_RULES
