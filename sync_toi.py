"""
sync_toi.py — Syncs avg TOI and player bio data from the modulekit/statviewtype endpoint.

This endpoint returns season-aggregate stats per team including:
  - ice_time_avg  : average seconds per game (float)
  - ice_time_per_game_avg : pre-formatted "MM:SS" string
  - birthcntry, hometown, height, shoots (bonus bio data)

Run:
    python pwhl/sync_toi.py            # sync all teams for current season
    python pwhl/sync_toi.py --migrate  # add columns first, then sync
    python pwhl/sync_toi.py --dry-run  # print updates without writing
"""

import argparse
import requests
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from db_config import get_db_url
from backfill import SEASON_ID

API_BASE    = "https://lscluster.hockeytech.com/feed/index.php"
API_KEY     = "446521baf8c38984"
CLIENT_CODE = "pwhl"

engine  = create_engine(get_db_url())
Session = sessionmaker(bind=engine)


def api_get(params: dict) -> dict:
    params.update({"key": API_KEY, "client_code": CLIENT_CODE, "fmt": "json"})
    r = requests.get(API_BASE, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def migrate(session):
    """Add new columns if they don't exist yet."""
    cols = {
        "players": [
            ("avg_toi_seconds", "INT DEFAULT NULL"),
            ("nationality",     "VARCHAR(100) DEFAULT NULL"),
            ("hometown",        "VARCHAR(200) DEFAULT NULL"),
            ("height",          "VARCHAR(10)  DEFAULT NULL"),
            ("shoots",          "VARCHAR(1)   DEFAULT NULL"),
        ]
    }
    for table, columns in cols.items():
        for col_name, col_def in columns:
            try:
                session.execute(text(
                    f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}"
                ))
                session.commit()
                print(f"  ✅ Added {table}.{col_name}")
            except Exception as e:
                session.rollback()
                if "Duplicate column" in str(e):
                    print(f"  — {table}.{col_name} already exists")
                else:
                    raise


def get_team_ids(session) -> list[int]:
    """Get all team IDs for the current season from the DB."""
    rows = session.execute(text("""
        SELECT DISTINCT team_id FROM teams WHERE season_id = :sid
    """), {"sid": SEASON_ID}).fetchall()
    return [r.team_id for r in rows]


def _parse_toi_seconds(val) -> int | None:
    """Parse ice_time_avg (float seconds string) → int seconds."""
    try:
        return round(float(val))
    except (TypeError, ValueError):
        return None


def fetch_team_players(team_id: int, player_type: str) -> list[dict]:
    """Fetch season stats for one team. player_type = 'skaters' or 'goalies'."""
    data = api_get({
        "feed":      "modulekit",
        "view":      "statviewtype",
        "type":      player_type,
        "season_id": SEASON_ID,
        "league_id": 1,
        "team_id":   team_id,
    })
    return data.get("SiteKit", {}).get("Statviewtype", [])


def fetch_all_goalies(team_ids: list) -> list[dict]:
    """Fetch goalie stats for all teams via modulekit/statviewtype."""
    goalies = []
    for tid in team_ids:
        try:
            data = api_get({
                "feed":      "modulekit",
                "view":      "statviewtype",
                "type":      "goalies",
                "season_id": SEASON_ID,
                "league_id": 1,
                "team_id":   tid,
            })
            goalies += data.get("SiteKit", {}).get("Statviewtype", [])
        except Exception as e:
            print(f"  [fetch_all_goalies] team {tid} error: {e}")
    return goalies


def sync_team(team_id: int, session, dry_run: bool = False) -> int:
    """Sync TOI + bio for all skaters and goalies on a team. Returns count updated."""
    players = []
    try:
        players += fetch_team_players(team_id, "skaters")
    except Exception as e:
        print(f"    ERROR fetching skaters team {team_id}: {e}")


    updated = 0
    for p in players:
        pid     = int(p.get("player_id", 0))
        if not pid:
            continue

        avg_toi = _parse_toi_seconds(p.get("ice_time_avg"))
        nat     = p.get("birthcntry") or None
        town    = p.get("hometown")   or None
        height  = p.get("height")     or None
        shoots  = p.get("shoots")     or None
        toi_str = p.get("ice_time_per_game_avg", "—")

        if dry_run:
            name = p.get("name", f"Player {pid}")
            print(f"    {name}: avg_toi={avg_toi}s ({toi_str}), "
                  f"nat={nat}, town={town}")
            updated += 1
            continue

        # Only update if player exists in DB (may not have played yet)
        result = session.execute(text("""
            UPDATE players
            SET avg_toi_seconds = :toi,
                nationality     = COALESCE(:nat,    nationality),
                hometown        = COALESCE(:town,   hometown),
                height          = COALESCE(:height, height),
                shoots          = COALESCE(:shoots, shoots)
            WHERE player_id = :pid
        """), {
            "toi":    avg_toi,
            "nat":    nat,
            "town":   town,
            "height": height,
            "shoots": shoots,
            "pid":    pid,
        })
        if result.rowcount > 0:
            updated += 1

    if not dry_run:
        session.commit()

    return updated


def sync_goalies(session, dry_run: bool = False) -> int:
    """Sync bio + TOI for all goalies via statviewfeed endpoint."""
    print("  Fetching goalies from modulekit...", end=" ", flush=True)
    try:
        team_ids = get_team_ids(session)
        goalies = fetch_all_goalies(team_ids)
    except Exception as e:
        print(f"ERROR: {e}")
        return 0

    print(f"{len(goalies)} goalies found")

    if goalies:
        print(f"  [goalie fields sample]: { {k:v for k,v in goalies[0].items() if any(x in k.lower() for x in ['ice','toi','time','birth','home','height','shoot','jersey','number'])} }")

    updated = 0
    for p in goalies:
        pid = int(p.get("player_id", 0))
        if not pid:
            continue

        nat    = p.get("birthcntry") or None
        town   = p.get("hometown")   or None
        height = p.get("height")     or None
        shoots = p.get("catches")    or p.get("shoots") or None
        jersey = p.get("jersey_number") or None

        if dry_run:
            name = p.get("name", f"Goalie {pid}")
            print(f"    {name}: nat={nat}, town={town}, height={height}, jersey={jersey}")
            updated += 1
            continue

        result = session.execute(text("""
            UPDATE players
            SET nationality   = COALESCE(:nat,    nationality),
                hometown      = COALESCE(:town,   hometown),
                height        = COALESCE(:height, height),
                shoots        = COALESCE(:shoots, shoots),
                jersey_number = COALESCE(:jersey, jersey_number)
            WHERE player_id = :pid
        """), {
            "nat":    nat,
            "town":   town,
            "height": height,
            "shoots": shoots,
            "jersey": int(jersey) if jersey else None,
            "pid":    pid,
        })
        if result.rowcount > 0:
            updated += 1

    if not dry_run:
        session.commit()

    return updated


def run_sync(dry_run: bool = False):
    session = Session()
    try:
        team_ids = get_team_ids(session)
        print(f"\n  Syncing skaters — {len(team_ids)} teams for season {SEASON_ID}...")

        total = 0
        for tid in sorted(team_ids):
            print(f"  Team {tid}...", end=" ", flush=True)
            n = sync_team(tid, session, dry_run=dry_run)
            print(f"{n} players")
            total += n

        print(f"\n  Syncing goalies...")
        total += sync_goalies(session, dry_run=dry_run)

        print(f"\n  ✅ Total players updated: {total}")
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--migrate",  action="store_true",
                        help="Add DB columns before syncing")
    parser.add_argument("--dry-run",  action="store_true",
                        help="Print updates without writing to DB")
    args = parser.parse_args()

    session = Session()
    if args.migrate:
        print("\n[1/2] Running migration...")
        migrate(session)
        print("\n[2/2] Syncing TOI data...")
    else:
        print("\nSyncing TOI data (use --migrate if columns don't exist yet)...")
    session.close()

    run_sync(dry_run=args.dry_run)
    print("\nDone.")
