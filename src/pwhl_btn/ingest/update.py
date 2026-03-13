"""
update.py — Incremental game update for PWHL analytics DB.
Finds the most recent game in the DB and fetches only new completed games.

Usage:
    python update.py              # fetch all new games since last DB entry
    python update.py --dry-run    # show what would be loaded without writing
"""

import argparse
import time
from datetime import date

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from pwhl_btn.db.db_config import get_db_url
from pwhl_btn.db.models import Base, Game, Team
from pwhl_btn.jobs.backfill import (
    SEASON_ID, RATE_LIMIT,
    fetch_schedule, load_teams, load_game, derive_result_type
)
try:
    from pwhl_btn.jobs.sync_toi import run_sync as sync_toi
except ImportError:
    sync_toi = None

engine  = create_engine(get_db_url())
Session = sessionmaker(bind=engine)


def get_final_game_ids_in_db(session) -> set[int]:
    """Returns game_ids already stored as final."""
    rows = session.execute(text("""
        SELECT game_id FROM games
        WHERE season_id = :sid AND game_status = 'final'
    """), {"sid": SEASON_ID}).fetchall()
    return {r.game_id for r in rows}


def get_new_games(already_final: set[int]) -> list[dict]:
    """Returns completed games from the API schedule not yet marked final in DB."""
    print(f"  Fetching season {SEASON_ID} schedule...")
    schedule = fetch_schedule(SEASON_ID)

    new = []
    for g in schedule:
        try:
            gid = int(g.get("id", 0))
        except (ValueError, TypeError):
            continue

        if gid in already_final:
            continue

        is_final = (
            str(g.get("game_status", "")).lower() == "final"
            or str(g.get("status", "")) == "4"
            or str(g.get("final", "0")) == "1"
        )
        if not is_final:
            continue

        new.append(g)

    return sorted(new, key=lambda g: int(g.get("id", 0)))


def run_update(dry_run: bool = False):
    session = Session()

    print(f"\nPWHL Incremental Update — Season {SEASON_ID}")
    print("=" * 50)

    # Ensure teams are current
    print("\n[1/3] Syncing teams...")
    load_teams(SEASON_ID, session)

    # Find games already marked final in DB
    print("\n[2/3] Checking DB for completed games...")
    already_final = get_final_game_ids_in_db(session)
    if already_final:
        print(f"  {len(already_final)} games already final in DB")
    else:
        print("  No final games in DB — run backfill.py first for historical data")
        print("  Run backfill_schedule.py to seed the full schedule")
        session.close()
        return

    # Find newly completed games
    print(f"\n[3/3] Checking for newly completed games...")
    new_games = get_new_games(already_final=already_final)

    if not new_games:
        print("  No new games found — DB is up to date")
        session.close()
        return

    print(f"  Found {len(new_games)} new game(s)")

    if dry_run:
        print("\n  [DRY RUN] Would load:")
        for g in new_games:
            print(f"    Game {g['id']} — {g['date_played']} — "
                  f"{g['home_team_name']} vs {g['visiting_team_name']}")
        session.close()
        return

    # Load new games
    ok_count = fail_count = 0
    for i, game in enumerate(new_games, 1):
        gid = int(game["id"])
        print(f"  [{i}/{len(new_games)}] Game {gid} "
              f"({game['date_played']} — {game['home_team_name']} vs {game['visiting_team_name']})...",
              end=" ", flush=True)
        if load_game(gid, session):
            ok_count += 1
            print("OK")
        else:
            fail_count += 1
            print("FAILED")
        time.sleep(RATE_LIMIT)

    session.close()
    print(f"\nDone: {ok_count} loaded, {fail_count} failed")

    # Refresh TOI averages after loading new games
    if ok_count > 0:
        print("\nRefreshing TOI averages...")
        if sync_toi:
            sync_toi()
        else:
            print("  [TOI] sync_toi not available, skipping")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Incremental PWHL game update")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show new games without loading them")
    args = parser.parse_args()
    run_update(dry_run=args.dry_run)
