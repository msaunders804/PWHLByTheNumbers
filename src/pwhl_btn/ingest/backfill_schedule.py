"""
backfill_schedule.py — Load the full Season 8 schedule into the games table,
including unplayed games as game_status='scheduled'.

Run ONCE to seed the schedule. After this, update.py will upsert final results
into the scheduled rows as games complete.

Usage:
    python backfill_schedule.py             # load all unplayed + any missing final games
    python backfill_schedule.py --dry-run   # preview without writing
"""

import argparse
import time
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from pwhl_btn.db.db_config import get_db_url
from pwhl_btn.jobs.backfill import (
    SEASON_ID, RATE_LIMIT,
    fetch_schedule, load_teams, load_game, upsert
)
from pwhl_btn.db.models import Base, Game

engine  = create_engine(get_db_url())
Session = sessionmaker(bind=engine)


def get_existing_game_ids(session) -> set[int]:
    rows = session.execute(text(
        "SELECT game_id FROM games WHERE season_id = :sid"
    ), {"sid": SEASON_ID}).fetchall()
    return {r.game_id for r in rows}


def get_team_id_map(session) -> dict[str, int]:
    """Map team_id strings from the API to confirmed DB team_ids."""
    rows = session.execute(text(
        "SELECT team_id FROM teams WHERE season_id = :sid"
    ), {"sid": SEASON_ID}).fetchall()
    return {str(r.team_id): r.team_id for r in rows}


def load_scheduled_game(g: dict, session, dry_run: bool = False) -> bool:
    """
    Insert a not-yet-played game as game_status='scheduled'.
    Only inserts team IDs, date, and game_id — no scores.
    """
    try:
        gid       = int(g["id"])
        game_date = datetime.strptime(g["date_played"], "%Y-%m-%d").date()
        home_id   = int(g["home_team"])
        away_id   = int(g["visiting_team"])

        if dry_run:
            print(f"    [DRY] Game {gid} — {game_date} — "
                  f"{g.get('home_team_name')} vs {g.get('visiting_team_name')} (scheduled)")
            return True

        upsert(session, Game, "game_id", gid,
               season_id        = SEASON_ID,
               date             = game_date,
               home_team_id     = home_id,
               away_team_id     = away_id,
               home_score       = None,
               away_score       = None,
               game_status      = "scheduled",
               result_type      = None,
               overtime_periods = 0,
               attendance       = None,
               venue            = None)
        session.commit()
        return True

    except Exception as e:
        session.rollback()
        print(f"    ERROR game {g.get('id')}: {e}")
        return False


def run(dry_run: bool = False):
    session = Session()

    print(f"\nPWHL Schedule Backfill — Season {SEASON_ID}")
    print("=" * 50)

    print("\n[1/3] Syncing teams...")
    load_teams(SEASON_ID, session)

    print("\n[2/3] Fetching full schedule from API...")
    schedule = fetch_schedule(SEASON_ID)
    print(f"  {len(schedule)} total games in season")

    existing = get_existing_game_ids(session)
    print(f"  {len(existing)} games already in DB")

    final_games   = []
    sched_games   = []
    already_have  = []

    for g in schedule:
        try:
            gid = int(g.get("id", 0))
        except (ValueError, TypeError):
            continue

        if gid in existing:
            already_have.append(gid)
            continue

        is_final = (
            str(g.get("game_status", "")).lower() == "final"
            or str(g.get("status", "")) == "4"
            or str(g.get("final", "0")) == "1"
        )
        if is_final:
            final_games.append(g)
        else:
            sched_games.append(g)

    print(f"\n  Already in DB:       {len(already_have)}")
    print(f"  Final to backfill:   {len(final_games)}")
    print(f"  Scheduled to insert: {len(sched_games)}")

    if not final_games and not sched_games:
        print("\n  Nothing to do — DB is already complete.")
        session.close()
        return

    print(f"\n[3/3] Loading games...")

    # Load any completed games not yet in DB via full load_game()
    if final_games:
        print(f"\n  Loading {len(final_games)} missing final game(s)...")
        ok = fail = 0
        for g in sorted(final_games, key=lambda x: int(x["id"])):
            gid = int(g["id"])
            print(f"    Game {gid} ({g['date_played']})...", end=" ", flush=True)
            if dry_run:
                print("[DRY]")
                ok += 1
            elif load_game(gid, session):
                print("OK")
                ok += 1
            else:
                print("FAILED")
                fail += 1
            time.sleep(RATE_LIMIT)
        print(f"  Final games: {ok} loaded, {fail} failed")

    # Insert unplayed games as 'scheduled'
    if sched_games:
        print(f"\n  Inserting {len(sched_games)} scheduled game(s)...")
        ok = fail = 0
        for g in sorted(sched_games, key=lambda x: int(x["id"])):
            if load_scheduled_game(g, session, dry_run=dry_run):
                ok += 1
            else:
                fail += 1
        print(f"  Scheduled games: {ok} inserted, {fail} failed")

    session.close()
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
