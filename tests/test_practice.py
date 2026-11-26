import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "soma"))

import curriculum  # noqa: E402
import practice  # noqa: E402

PAGES = [
    {"source": "kinyarwanda_s4", "audience": "student", "unit": "6: IKORANABUHANGA", "page": 128, "printed_page": 118,
     "text": "118 Ikinyarwanda Umwaka wa 4 Amashuri yisumbuye Igitabo cy’umunyeshuri UMWANDIKO: IKORANABUHANGA mu gukemura ibibazo"},
    {"source": "kinyarwanda_s4", "audience": "student", "unit": "6: IKORANABUHANGA", "page": 129, "printed_page": 119,
     "text": "119 Ikinyarwanda Umwaka wa 4 Amashuri yisumbuye Igitabo cy’umunyeshuri Ikoranabuhanga rifasha abahinzi"},
    {"source": "french_s4", "audience": "student", "unit": "3: L’HOMME INTEGRE", "page": 28, "printed_page": 21, "text": "a"},
    {"source": "french_s4", "audience": "student", "unit": "3: L’homme", "page": 39, "printed_page": 32, "text": "b"},
    {"source": "french_s4", "audience": "student", "unit": "4: LE PROGRES", "page": 45, "printed_page": 38, "text": "c"},
]


def fake_book(monkeypatch):
    for cached in (curriculum.units, curriculum.running_header):
        cached.cache_clear()
    monkeypatch.setattr(curriculum, "load_chunks", lambda: PAGES)


def test_the_table_of_contents_comes_from_the_book(monkeypatch):
    fake_book(monkeypatch)
    assert [u["title"] for u in curriculum.units("rw")] == ["Ikoranabuhanga"]


def test_running_headers_are_merged_into_their_unit(monkeypatch):
    fake_book(monkeypatch)
    french = curriculum.units("fr")
    assert [u["title"] for u in french] == ["L’homme integre", "Le progres"]
    assert french[0]["last_page"] == 39


def test_reading_pages_hide_page_numbers_and_book_headers(monkeypatch):
    fake_book(monkeypatch)
    pages = curriculum.unit_pages("rw", "rw-1")
    assert pages[0]["text"].startswith("UMWANDIKO") and pages[1]["text"] == "Ikoranabuhanga rifasha abahinzi"


def test_two_greens_move_up_and_two_yellows_give_more_help():
    assert practice.next_step(4, 0, passed=True, tries=1) == (4, 1)      # one green: not yet
    assert practice.next_step(4, 1, passed=True, tries=2) == (5, 0)      # two greens in a row: up
    assert practice.next_step(4, 1, passed=False, tries=3) == (4, -1)    # a yellow breaks the green run
    assert practice.next_step(4, -1, passed=False, tries=3) == (3, 0)    # two yellows: easier, more help
    assert practice.next_step(4, 0, passed=True, tries=3) == (4, -1)     # passed only after the example: yellow
    assert practice.next_step(9, 1, True, 1) == (9, 2) and practice.next_step(1, -1, False, 3) == (1, -2)


def test_each_level_gives_a_different_amount_of_help():
    assert "guided" in practice.LEVEL_HELP[1] and "partial help" in practice.LEVEL_HELP[2]
    assert "free speaking" in practice.LEVEL_HELP[3]
    assert "every try" in practice.HINT_POLICY[1] and "second try" in practice.HINT_POLICY[3]


def test_tasks_rotate_between_debate_interview_and_presentation():
    assert [practice.scenario_for(["x"] * n) for n in range(4)] == ["debate", "interview", "presentation", "debate"]


def test_levels_and_placement_start():
    assert [practice.level_of(d) for d in (1, 3, 4, 6, 7, 9)] == [1, 1, 2, 2, 3, 3]
    assert [practice.start_difficulty(n) for n in range(4)] == [1, 3, 5, 7]


def test_harder_tasks_ask_for_longer_answers():
    assert "one short sentence" in practice.LENGTH_GUIDE[1]
    assert "one minute" in practice.LENGTH_GUIDE[8]


def test_tasks_are_generated_not_written_in_advance(monkeypatch):
    fake_book(monkeypatch)
    sent = {}

    def model(prompt, system="", names=()):
        sent["system"] = system
        return "Inshuti yawe ivuze ko ikoranabuhanga ryangiza umuco..."
    monkeypatch.setattr(practice, "call_model", model)
    task, scenario = practice.new_task("rw", "rw-1", 5, recent=["old task"])
    assert task.startswith("Inshuti") and scenario == "interview"
    assert "Write ONE task in Kinyarwanda" in sent["system"] and "Difficulty 5 of 9. Level 2, partial help" in sent["system"]
    assert "old task" in sent["system"] and "Ikoranabuhanga" in sent["system"]


def test_assessment_gives_hints_first_and_an_example_only_on_the_last_try(monkeypatch):
    sent = {}

    def model(prompt, system="", names=()):
        sent["system"] = system
        return "Watangiye neza. Inama: ...\nTASK_PASSED: no"
    monkeypatch.setattr(practice, "call_model", model)
    result = practice.assess("rw", 4, "Vuga icyo utekereza", "Ntabwo", tries=1)
    assert result == {"reply": "Watangiye neza. Inama: ...", "passed": False, "finished": False}
    assert "Give ONE hint only if the try is not yet right" in sent["system"] and "Everything you write is in Kinyarwanda" in sent["system"]
    assert practice.assess("rw", 4, "task", "answer", tries=3)["finished"] is True
