"""ETL pipeline: raw practice events -> clean daily totals for the teacher dashboard.

Design: ETL (not ELT), because the data is about minors. The events table already holds no
answers or recordings, and the transform keeps only totals per learner, day and language.
Names are never copied into the totals; the dashboard joins them at display time.

Incremental: only events newer than the watermark (minus a small overlap for late rows) are read.
Idempotent: totals for every affected learner-day are recomputed from all of that day's events
and upserted on (user_id, day, language), so re-runs and backfills never create duplicates.
Backfill: run(start="2026-11-01", end="2026-11-30") recomputes those days; the watermark is not moved.
"""

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

import accounts
import fluency

PIPELINE = "daily_stats"
KIGALI = timezone(timedelta(hours=2))      # Rwanda has no daylight saving time
OVERLAP = timedelta(minutes=10)
PAGE_SIZE = 1000
EPOCH = "2026-01-01T00:00:00+00:00"


def parse(timestamp):
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def local_day(timestamp):
    return parse(timestamp).astimezone(KIGALI).date()


def day_bounds(first_day, last_day):
    """UTC start of first_day and end of last_day, in Rwanda time."""
    start = datetime.combine(first_day, datetime.min.time(), KIGALI)
    end = datetime.combine(last_day + timedelta(days=1), datetime.min.time(), KIGALI)
    return start.astimezone(timezone.utc).isoformat(), end.astimezone(timezone.utc).isoformat()


# --- Extract ---

def read_watermark():
    rows = accounts.select("etl_state", pipeline=f"eq.{PIPELINE}")
    return rows[0]["watermark"] if rows else EPOCH


def save_watermark(value):
    accounts.insert("etl_state", [{"pipeline": PIPELINE, "watermark": value}], upsert_on="pipeline")


def fetch_events(**filters):
    rows, offset = [], 0
    while True:
        page = accounts.select("events", order="created_at,id", limit=str(PAGE_SIZE), offset=str(offset), **filters)
        rows += page
        if len(page) < PAGE_SIZE:
            return rows
        offset += PAGE_SIZE


# --- Transform (pure: easy to test) ---

def aggregate(events):
    """Daily totals per (user, day, language) from raw events."""
    groups = defaultdict(list)
    for event in events:
        groups[(event["user_id"], local_day(event["created_at"]), event["language"])].append(event)

    rows = []
    for (user_id, day, language), items in groups.items():
        items.sort(key=lambda e: e["created_at"])
        tasks = [e for e in items if e["kind"] == "task"]
        sessions = [e for e in items if e["kind"] == "session_end"]
        speeds = [e["wpm"] for e in items if e.get("wpm")]
        pauses = [e["pauses_per_min"] for e in items if e.get("pauses_per_min") is not None]
        fillers = [e["fillers_per_100"] for e in items if e.get("fillers_per_100") is not None]
        with_level = [e for e in items if e.get("difficulty")]
        rows.append({
            "user_id": user_id, "day": day.isoformat(), "language": language,
            "class_id": items[-1].get("class_id"),
            "sessions": len(sessions),
            "practice_minutes": round(sum(e.get("seconds") or 0 for e in sessions) / 60, 1),
            "tasks": len(tasks),
            "passed": sum(1 for e in tasks if e.get("passed")),
            "avg_wpm": round(sum(speeds) / len(speeds), 1) if speeds else None,
            "avg_pauses": round(sum(pauses) / len(pauses), 1) if pauses else None,
            "avg_fillers": round(sum(fillers) / len(fillers), 1) if fillers else None,
            "difficulty": with_level[-1]["difficulty"] if with_level else None,
            "last_active": items[-1]["created_at"],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
    return rows


# --- Load ---

def load(rows):
    if rows:
        accounts.insert("daily_stats", rows, upsert_on="user_id,day,language")
    return len(rows)


def recompute(user_ids, first_day, last_day):
    """Recompute whole days from all their events, so the result never depends on run order."""
    start, end = day_bounds(first_day, last_day)
    filters = {"and": f"(created_at.gte.{start},created_at.lt.{end})"}
    if user_ids is not None:
        filters["user_id"] = f"in.({','.join(sorted(user_ids))})"
    return load(aggregate(fetch_events(**filters)))


def run(start=None, end=None):
    """Incremental run (no dates) or backfill (start and end as YYYY-MM-DD). Returns rows loaded."""
    if start or end:
        first = date.fromisoformat(start or end)
        last = date.fromisoformat(end or start)
        return recompute(None, first, last)

    watermark = read_watermark()
    since = (parse(watermark) - OVERLAP).isoformat()
    new_events = fetch_events(created_at=f"gt.{since}")
    if not new_events:
        return 0
    days = [local_day(e["created_at"]) for e in new_events]
    loaded = recompute({e["user_id"] for e in new_events}, min(days), max(days))
    newest = max(e["created_at"] for e in new_events)
    if newest > watermark:
        save_watermark(newest)            # only moves forward, and only after a successful load
    return loaded


# --- Read side for the dashboard ---

def learner_summaries(learners, days=7):
    """Totals over the last few days for each learner, plus their level per language."""
    if not learners:
        return []
    ids = [l["user_id"] for l in learners]
    since = (datetime.now(KIGALI).date() - timedelta(days=days - 1)).isoformat()
    stats = accounts.select("daily_stats", user_id=f"in.({','.join(ids)})", day=f"gte.{since}")
    levels = accounts.select("levels", user_id=f"in.({','.join(ids)})")
    starts = start_levels(ids)
    out = []
    for learner in learners:
        mine = [s for s in stats if s["user_id"] == learner["user_id"]]
        tasks = sum(s["tasks"] for s in mine)
        passed = sum(s["passed"] for s in mine)
        speeds = [s["avg_wpm"] for s in mine if s.get("avg_wpm")]
        out.append({
            "user_id": learner["user_id"],
            "name": learner["name"],
            "start_levels": {lang: level for (uid, lang), level in starts.items() if uid == learner["user_id"]},
            "levels": {l["language"]: (l["difficulty"] - 1) // 3 + 1 for l in levels if l["user_id"] == learner["user_id"]},
            "minutes": round(sum(s["practice_minutes"] for s in mine), 1),
            "sessions": sum(s["sessions"] for s in mine),
            "tasks": tasks, "passed": passed,
            "avg_wpm": round(sum(speeds) / len(speeds)) if speeds else None,
            "last_active": max((s["last_active"] for s in mine if s.get("last_active")), default=None),
            "needs_help": tasks >= 3 and passed / tasks < 0.4,
        })
    return out


def start_levels(user_ids):
    """{(user_id, language): level} from each learner's first level (set by the placement check)."""
    if not user_ids:
        return {}
    rows = accounts.select("events", user_id=f"in.({','.join(user_ids)})", kind="eq.level",
                           select="user_id,language,difficulty,created_at", order="created_at")
    first = {}
    for row in rows:
        first.setdefault((row["user_id"], row["language"]), (row["difficulty"] - 1) // 3 + 1)
    return first


def learner_progress(user_id, language, days=30):
    """One learner's progress in one language: start and current level, and totals per day."""
    today = datetime.now(KIGALI).date()
    recompute({user_id}, today, today)                       # today's numbers are always fresh
    since = (today - timedelta(days=days - 1)).isoformat()
    rows = accounts.select("daily_stats", user_id=f"eq.{user_id}", language=f"eq.{language}",
                           day=f"gte.{since}", order="day")
    current = accounts.select("levels", user_id=f"eq.{user_id}", language=f"eq.{language}")
    difficulty = current[0]["difficulty"] if current else None
    start = start_levels([user_id]).get((user_id, language))
    level_by_day, last = [], None
    for row in rows:                                         # carry the level over days without a level change
        last = row.get("difficulty") or last
        level_by_day.append({"day": row["day"], "difficulty": last, "level": (last - 1) // 3 + 1 if last else None,
                             "minutes": row["practice_minutes"], "tasks": row["tasks"], "passed": row["passed"],
                             "avg_wpm": row.get("avg_wpm"), "avg_pauses": row.get("avg_pauses"),
                             "avg_fillers": row.get("avg_fillers")})
    speeds = [r["avg_wpm"] for r in rows if r.get("avg_wpm")]
    pauses = [r["avg_pauses"] for r in rows if r.get("avg_pauses") is not None]
    fillers = [r["avg_fillers"] for r in rows if r.get("avg_fillers") is not None]
    return {
        "language": language,
        "start_level": start,
        "difficulty": difficulty,
        "level": (difficulty - 1) // 3 + 1 if difficulty else None,
        "step_in_level": (difficulty - 1) % 3 + 1 if difficulty else None,     # 1-3 inside the level
        "days": level_by_day,
        "totals": {"days_practised": sum(1 for r in rows if r["tasks"] or r["sessions"]),
                   "minutes": round(sum(r["practice_minutes"] for r in rows), 1),
                   "tasks": sum(r["tasks"] for r in rows), "passed": sum(r["passed"] for r in rows),
                   "avg_wpm": round(sum(speeds) / len(speeds)) if speeds else None,
                   "avg_pauses": round(sum(pauses) / len(pauses), 1) if pauses else None,
                   "avg_fillers": round(sum(fillers) / len(fillers), 1) if fillers else None},
        "target_wpm": list(fluency.LANGUAGE_RULES.get(language, fluency.LANGUAGE_RULES["en"])["speed"]),
    }
