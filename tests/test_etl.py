import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "soma"))

import pytest  # noqa: E402

import etl  # noqa: E402

KEYS = {"daily_stats": ("user_id", "day", "language"), "etl_state": ("pipeline",), "levels": ("user_id", "language")}


class FakeDatabase:
    """Just enough of Supabase for the pipeline: filters gt/gte/lt/in and upserts."""

    def __init__(self, events):
        self.tables = {"events": events, "daily_stats": [], "etl_state": [], "levels": []}

    def select(self, table, **filters):
        rows = list(self.tables[table])
        for column, rule in filters.items():
            if column in ("select", "order", "limit", "offset"):
                continue
            if column == "and":
                for part in rule.strip("()").split(","):
                    col, op, value = part.split(".", 2)
                    rows = [r for r in rows if self._match(r[col], op, value)]
                continue
            op, value = rule.split(".", 1)
            rows = [r for r in rows if self._match(r[column], op, value)]
        offset, limit = int(filters.get("offset", 0)), int(filters.get("limit", 10**9))
        return rows[offset:offset + limit]

    @staticmethod
    def _match(actual, op, value):
        if op == "eq":
            return str(actual) == value
        if op == "in":
            return actual in value.strip("()").split(",")
        a, v = etl.parse(actual), etl.parse(value)
        return {"gt": a > v, "gte": a >= v, "lt": a < v}[op]

    def insert(self, table, rows, upsert_on=None):
        for row in rows:
            key = tuple(row[k] for k in KEYS[table])
            self.tables[table] = [r for r in self.tables[table] if tuple(r[k] for k in KEYS[table]) != key]
            self.tables[table].append(row)
        return rows


def event(user, kind, when, **values):
    return {"user_id": user, "class_id": "c1", "kind": kind, "language": "rw", "created_at": when, **values}


@pytest.fixture
def database(monkeypatch):
    db = FakeDatabase([
        event("u1", "task", "2026-11-27T08:00:00+00:00", difficulty=3, passed=True, wpm=90),
        event("u1", "task", "2026-11-27T08:05:00+00:00", difficulty=4, passed=False, wpm=70),
        event("u1", "session_end", "2026-11-27T08:10:00+00:00", seconds=240),
        event("u2", "task", "2026-11-27T09:00:00+00:00", difficulty=1, passed=True),
    ])
    monkeypatch.setattr(etl.accounts, "select", db.select)
    monkeypatch.setattr(etl.accounts, "insert", db.insert)
    return db


def test_daily_totals_are_correct(database):
    etl.run()
    aline = next(r for r in database.tables["daily_stats"] if r["user_id"] == "u1")
    assert (aline["tasks"], aline["passed"], aline["sessions"], aline["practice_minutes"]) == (2, 1, 1, 4.0)
    assert aline["avg_wpm"] == 80.0 and aline["difficulty"] == 4


def test_rerun_creates_no_duplicates(database):
    etl.run()
    first = sorted((r["user_id"], r["day"], r["tasks"]) for r in database.tables["daily_stats"])
    etl.run()
    etl.run()
    again = sorted((r["user_id"], r["day"], r["tasks"]) for r in database.tables["daily_stats"])
    assert first == again and len(again) == 2


def test_watermark_moves_forward_and_new_events_update_the_same_day(database):
    etl.run()
    assert database.tables["etl_state"][0]["watermark"] == "2026-11-27T09:00:00+00:00"
    database.tables["events"].append(event("u1", "task", "2026-11-27T10:00:00+00:00", difficulty=5, passed=True))
    etl.run()
    aline = next(r for r in database.tables["daily_stats"] if r["user_id"] == "u1")
    assert aline["tasks"] == 3 and len(database.tables["daily_stats"]) == 2
    assert database.tables["etl_state"][0]["watermark"] == "2026-11-27T10:00:00+00:00"


def test_backfill_recomputes_a_past_range_without_moving_the_watermark(database):
    etl.run()
    database.tables["daily_stats"].clear()
    etl.run(start="2026-11-27", end="2026-11-27")
    assert len(database.tables["daily_stats"]) == 2
    assert database.tables["etl_state"][0]["watermark"] == "2026-11-27T09:00:00+00:00"


def test_days_follow_rwanda_time():
    # 23:30 UTC on the 27th is already the 28th in Kigali
    assert str(etl.local_day("2026-11-27T23:30:00+00:00")) == "2026-11-28"


def test_no_names_or_answers_reach_the_dashboard_table(database):
    etl.run()
    for row in database.tables["daily_stats"]:
        assert not {"name", "answer", "text", "audio"} & set(row)


def test_learner_progress_shows_start_level_current_level_and_days(database, monkeypatch):
    database.tables["events"] += [
        event("u1", "level", "2026-11-25T08:00:00+00:00", difficulty=2),    # placement: level 1
        event("u1", "task", "2026-11-25T08:05:00+00:00", difficulty=2, passed=True),
        event("u1", "level", "2026-11-27T08:06:00+00:00", difficulty=5),    # now level 2
    ]
    database.tables["levels"].append({"user_id": "u1", "language": "rw", "difficulty": 5})
    monkeypatch.setattr(etl, "datetime", type("FixedNow", (etl.datetime,), {
        "now": classmethod(lambda cls, tz=None: etl.datetime(2026, 11, 27, 12, tzinfo=tz))}))
    etl.run(start="2026-11-25", end="2026-11-27")
    data = etl.learner_progress("u1", "rw")
    assert data["start_level"] == 1 and data["level"] == 2 and data["step_in_level"] == 2
    assert [d["day"] for d in data["days"]] == ["2026-11-25", "2026-11-27"]
    assert data["days"][0]["level"] == 1 and data["days"][-1]["level"] == 2
    assert data["totals"]["tasks"] == 3 and data["totals"]["days_practised"] == 2
