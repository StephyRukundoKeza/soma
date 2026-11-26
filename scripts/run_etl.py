"""Run the dashboard ETL by hand.

    python scripts/run_etl.py                                    # new events since the last run
    python scripts/run_etl.py --start 2026-11-27 --end 2026-11-30  # backfill (recompute those days)
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "soma"))

import etl  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Load practice events into the daily totals.")
    parser.add_argument("--start", help="first day to recompute (YYYY-MM-DD)")
    parser.add_argument("--end", help="last day to recompute (YYYY-MM-DD)")
    args = parser.parse_args()
    loaded = etl.run(args.start, args.end)
    print(f"Loaded {loaded} learner-day rows into daily_stats.")


if __name__ == "__main__":
    main()
