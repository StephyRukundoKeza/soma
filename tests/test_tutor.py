import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "soma"))

import tutor  # noqa: E402

PAGE = {"source": "gscs_s4", "page": 20, "printed_page": 12,
        "text": "Active listening is the ability to listen attentively and not just hearing."}


def fake_model(reply, sent):
    def call(prompt, system="", names=()):
        sent.update(prompt=prompt, system=system)
        return reply
    return call


def test_every_step_has_a_goal_a_pass_rule_and_book_pages_in_every_language():
    for step in tutor.LEARNING_SEQUENCE:
        assert step["goal"] and step["check"]
        assert all(step["pages"][lang] for lang in ("en", "rw", "sw", "fr"))


def test_kinyarwanda_is_practised_in_kinyarwanda_from_the_kinyarwanda_book(monkeypatch):
    sent = {}
    page = {"source": "kinyarwanda_s4", "page": 84, "printed_page": 74,
            "text": "Uko bajya impaka: ufashe ijambo bwa mbere asobanura uko yumva insanganyamatsiko."}
    monkeypatch.setattr(tutor, "load_chunks", lambda: [page])
    monkeypatch.setattr(tutor, "call_model", fake_model("Gerageza.\nSTEP_PASSED: no", sent))
    tutor.coach(1, "Ndumva ufite ukuri ariko...", language="rw")
    assert "practised in Kinyarwanda" in sent["system"]
    assert "Everything happens in Kinyarwanda" in sent["system"]
    assert "[Ikinyarwanda S4, p. 74]" in sent["system"] and "Mbabarira" in sent["system"]


def test_spoken_answers_are_marked_with_their_speed(monkeypatch):
    sent = {}
    monkeypatch.setattr(tutor, "load_chunks", lambda: [PAGE])
    monkeypatch.setattr(tutor, "call_model", fake_model("ok\nSTEP_PASSED: no", sent))
    spoken = {"seconds": 4.2, "wpm": 86, "target_wpm": [100, 160], "pauses": 1, "long_pauses": 0, "fillers": 2,
              "repeats": 0, "phrases": ["i think"]}
    tutor.coach(0, "So I think football is best", spoken=spoken)
    assert "spoken; measured by SOMA: spoken for 4 s; speed 86 words per minute (comfortable range 100-160)" in sent["prompt"]
    assert "taught polite phrases used: i think" in sent["prompt"]


def test_tutor_gives_hints_before_answers_and_uses_the_book(monkeypatch):
    sent = {}
    monkeypatch.setattr(tutor, "load_chunks", lambda: [PAGE])
    monkeypatch.setattr(tutor, "call_model", fake_model("Try again.\nSTEP_PASSED: no", sent))
    tutor.coach(0, "I don't agree with you.", language="rw")
    assert "Never show a model answer before they try" in sent["system"]
    assert "ONE hint" in sent["system"]
    assert "[GSCS S4, p. 12]" in sent["system"] and "Active listening" in sent["system"]
    assert "Everything happens in Kinyarwanda" in sent["system"]


def test_passing_a_step_is_read_and_hidden_from_the_learner(monkeypatch):
    monkeypatch.setattr(tutor, "load_chunks", lambda: [PAGE])
    monkeypatch.setattr(tutor, "call_model", fake_model("Well done!\nSTEP_PASSED: yes", {}))
    result = tutor.coach(0, "So you mean the trip is too expensive?")
    assert result["passed"] is True and "STEP_PASSED" not in result["reply"]


def test_opening_a_step_never_counts_as_passing(monkeypatch):
    monkeypatch.setattr(tutor, "load_chunks", lambda: [PAGE])
    monkeypatch.setattr(tutor, "call_model", fake_model("Here is your situation.\nSTEP_PASSED: yes", {}))
    assert tutor.coach(0, "")["passed"] is False


def test_only_recent_history_is_sent(monkeypatch):
    sent = {}
    monkeypatch.setattr(tutor, "load_chunks", lambda: [PAGE])
    monkeypatch.setattr(tutor, "call_model", fake_model("ok\nSTEP_PASSED: no", sent))
    history = [{"role": "learner", "text": f"try {i}"} for i in range(20)]
    tutor.coach(0, "latest", history)
    assert "try 19" in sent["prompt"] and "try 0\n" not in sent["prompt"]
