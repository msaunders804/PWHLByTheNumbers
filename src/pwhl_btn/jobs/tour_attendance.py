"""
tour_attendance.py — Takeover Tour attendance chart

Queries all games played at non-home venues and prints a bar chart to the CLI.
Combines across all seasons by default.

Usage:
    python -m pwhl_btn.jobs.tour_attendance
    python -m pwhl_btn.jobs.tour_attendance --season 8
    python -m pwhl_btn.jobs.tour_attendance --seasons 5 8
    python -m pwhl_btn.jobs.tour_attendance --sort total
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from sqlalchemy import text
from pwhl_btn.db.db_config import get_engine

DATA_FILE = Path(__file__).resolve().parents[3] / "data" / "expansion_cities.json"
BAR_WIDTH  = 20


def _bar(value: int, max_value: int) -> str:
    filled = round((value / max_value) * BAR_WIDTH) if max_value else 0
    return "#" * filled + "-" * (BAR_WIDTH - filled)


def _fetch_seasons(conn) -> list[int]:
    rows = conn.execute(text(
        "SELECT DISTINCT season_id FROM games "
        "WHERE game_status='final' AND attendance IS NOT NULL "
        "ORDER BY season_id"
    )).fetchall()
    return [r.season_id for r in rows]


def main() -> None:
    parser = argparse.ArgumentParser(description="Takeover Tour attendance chart")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--season",  type=int,        help="Single season ID")
    group.add_argument("--seasons", type=int, nargs="+", help="One or more season IDs")
    parser.add_argument("--sort", choices=["avg", "total", "games"], default="avg",
                        help="Sort by: avg (default), total, or game count")
    args = parser.parse_args()

    home_venues = set(json.loads(DATA_FILE.read_text(encoding="utf-8"))["existing_pwhl_home_venues"])

    engine = get_engine(pool_pre_ping=True)
    with engine.connect() as conn:
        all_seasons = _fetch_seasons(conn)

        if args.season:
            seasons = [args.season]
        elif args.seasons:
            seasons = args.seasons
        else:
            seasons = all_seasons

        placeholders = ", ".join(f":s{i}" for i in range(len(seasons)))
        params = {f"s{i}": s for i, s in enumerate(seasons)}

        rows = conn.execute(text(f"""
            SELECT g.venue,
                   g.season_id,
                   COUNT(*)          AS game_count,
                   SUM(g.attendance) AS total_att
            FROM games g
            WHERE g.season_id   IN ({placeholders})
              AND g.game_status = 'final'
              AND g.venue       IS NOT NULL
              AND g.attendance  IS NOT NULL
            GROUP BY g.venue, g.season_id
        """), params).fetchall()

    # Aggregate across seasons per venue
    by_venue: dict[str, dict] = defaultdict(lambda: {"total_att": 0, "game_count": 0})
    for r in rows:
        if r.venue in home_venues:
            continue
        by_venue[r.venue]["total_att"]  += int(r.total_att or 0)
        by_venue[r.venue]["game_count"] += int(r.game_count)

    data = [
        {
            "venue":      venue,
            "total_att":  v["total_att"],
            "game_count": v["game_count"],
            "avg_att":    round(v["total_att"] / v["game_count"]) if v["game_count"] else 0,
        }
        for venue, v in by_venue.items()
    ]

    sort_key = {"avg": "avg_att", "total": "total_att", "games": "game_count"}[args.sort]
    data.sort(key=lambda r: -r[sort_key])

    if not data:
        print("  No Takeover Tour games found.")
        return

    max_avg = max(r["avg_att"] for r in data)
    season_label = (f"Season {seasons[0]}" if len(seasons) == 1
                    else "Seasons " + " + ".join(str(s) for s in seasons))

    print()
    print(f"  PWHL TAKEOVER TOUR  {season_label}  (sorted by {args.sort})")
    print(f"  {'-' * 68}")
    print(f"  {'Venue':<34}  {'Avg':>6}  {'Games':>5}  {'Total':>7}  Chart")
    print(f"  {'-' * 68}")
    for r in data:
        bar = _bar(r["avg_att"], max_avg)
        print(f"  {r['venue']:<34}  {r['avg_att']:>6,}  {r['game_count']:>5}  "
              f"{r['total_att']:>7,}  {bar}")
    print()


if __name__ == "__main__":
    main()
