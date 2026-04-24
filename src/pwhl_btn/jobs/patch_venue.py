"""
patch_venue.py — Backfill missing venue (and attendance) for existing games.

Finds games in the DB where venue IS NULL, fetches the gamesummary from the
PWHL API, and updates venue (and attendance if also missing).  Does not touch
any other columns.

Usage:
    python -m pwhl_btn.jobs.patch_venue --season 5
    python -m pwhl_btn.jobs.patch_venue --season 5 --dry-run
    python -m pwhl_btn.jobs.patch_venue          # all seasons with null venues
"""
from __future__ import annotations

import argparse
import time

import requests
from sqlalchemy import text

from pwhl_btn.db.db_config import get_engine

API_BASE    = "https://lscluster.hockeytech.com/feed/index.php"
API_KEY     = "446521baf8c38984"
CLIENT_CODE = "pwhl"
RATE_LIMIT  = 0.5


def fetch_venue(game_id: int) -> tuple[str | None, int | None]:
    """Return (venue, attendance) from the API gamesummary, or (None, None) on error."""
    try:
        r = requests.get(API_BASE, params={
            "feed": "gc", "tab": "gamesummary",
            "game_id": game_id,
            "key": API_KEY, "client_code": CLIENT_CODE, "fmt": "json",
        }, timeout=15)
        r.raise_for_status()
        gs   = r.json()["GC"]["Gamesummary"]
        meta = gs.get("meta", {})

        venue = gs.get("venue") or meta.get("venue") or None
        if venue:
            venue = venue.strip() or None

        raw_att = meta.get("attendance")
        attendance = int(raw_att) if raw_att and str(raw_att).strip() not in ("", "0") else None

        return venue, attendance
    except Exception as e:
        print(f"    API error: {e}")
        return None, None


def main() -> None:
    parser = argparse.ArgumentParser(description="Patch missing venue/attendance from API")
    parser.add_argument("--season", type=int, help="Limit to a specific season_id")
    parser.add_argument("--dry-run", action="store_true", help="Fetch but do not write to DB")
    args = parser.parse_args()

    engine = get_engine(pool_pre_ping=True)

    with engine.connect() as conn:
        query = "SELECT game_id, season_id FROM games WHERE venue IS NULL AND game_status = 'final'"
        params: dict = {}
        if args.season:
            query += " AND season_id = :sid"
            params["sid"] = args.season
        query += " ORDER BY season_id, game_id"

        rows = conn.execute(text(query), params).fetchall()

    if not rows:
        print("  No games with missing venue found.")
        return

    season_label = f"season {args.season}" if args.season else "all seasons"
    print(f"\n  Patching venue for {len(rows)} games ({season_label})"
          + ("  [DRY RUN]" if args.dry_run else ""))
    print(f"  {'-' * 60}")

    updated = skipped = failed = 0

    with engine.begin() as conn:
        for i, row in enumerate(rows, 1):
            gid = row.game_id
            print(f"  [{i:3d}/{len(rows)}] game {gid} ...", end=" ", flush=True)

            venue, attendance = fetch_venue(gid)

            if not venue:
                print("no venue in API — skipping")
                skipped += 1
                time.sleep(RATE_LIMIT)
                continue

            print(f"{venue}", end="")

            if not args.dry_run:
                conn.execute(text("""
                    UPDATE games
                    SET venue      = :venue,
                        attendance = COALESCE(attendance, :att)
                    WHERE game_id  = :gid
                """), {"venue": venue, "att": attendance, "gid": gid})
                print("  -> saved")
            else:
                print("  -> [dry-run]")

            updated += 1
            time.sleep(RATE_LIMIT)

    print(f"\n  Done: {updated} updated, {skipped} skipped (no API venue), {failed} errors")


if __name__ == "__main__":
    main()
