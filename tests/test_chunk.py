import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "soma"))

from chunk import find_headings, repair_text, split_words  # noqa: E402


def test_shifted_font_text_is_repaired():
    assert repair_text("WKH\x03VRFLHW\\") == "the society"


def test_normal_text_is_not_changed():
    text = "These help in reducing the barrier.\n35"
    assert repair_text(text) == text
    assert repair_text("Sport WKH\x03VRFLHW\\") == "Sport the society"


def test_gscs_style_unit_heading_is_found():
    page = "2\n2\nSocial Cohesion\nUnit\n1\nKey unit competence: ..."
    assert find_headings(page) == [("1", "1: Social Cohesion")]


def test_table_of_contents_lines_are_ignored():
    assert find_headings("UNIT 4: EFFECTIVE COMMUNICATION ............ 42") == []


def test_chunks_overlap_and_skip_scraps():
    words = " ".join(f"w{i}" for i in range(700))
    pieces = split_words(words)
    assert len(pieces) == 3
    assert pieces[0].split()[-50:] == pieces[1].split()[:50]
    assert split_words("too short") == []