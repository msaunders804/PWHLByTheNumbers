"""
backfill.py — Fetch all Season 8 games from the PWHL API and load into MySQL.

Usage:
    python backfill.py                  # full season 8 backfill
    python backfill.py --game 210       # single game test
    python backfill.py --limit 5        # first 5 games only
    python backfill.py --resume         # skip games already in DB
"""

import os, sys, time, argparse, requests
from datetime import datetime, date
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from pwhl_btn.db.models import Base, Game, Team, Player, PlayerGameStats, GoalieGameStats

from pwhl_btn.db.db_config import get_db_url
DATABASE_URL = get_db_url()

SEASON_ID   = 8
API_BASE    = "https://lscluster.hockeytech.com/feed/index.php"
API_KEY     = "446521baf8c38984"
CLIENT_CODE = "pwhl"
RATE_LIMIT  = 0.5

engine  = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


# ── API helpers ────────────────────────────────────────────────────────────────
def api_get(params: dict) -> dict:
    params.update({"key": API_KEY, "client_code": CLIENT_CODE, "fmt": "json"})
    r = requests.get(API_BASE, params=params, timeout=15)
    r.raise_for_status()
    return r.json()

def fetch_schedule(season_id):
    return api_get({"feed": "modulekit", "view": "schedule", "season_id": season_id})["SiteKit"]["Schedule"]

def fetch_teams(season_id):
    """Extract unique teams from the season schedule."""
    schedule = fetch_schedule(season_id)
    teams = {}
    for game in schedule:
        for id_key, name_key, code_key in [
            ("home_team",     "home_team_name",     "home_team_code"),
            ("visiting_team", "visiting_team_name", "visiting_team_code"),
        ]:
            tid = game.get(id_key)
            if not tid:
                continue
            if tid not in teams:
                teams[tid] = {
                    "id":   tid,
                    "name": game.get(name_key, f"Team {tid}"),
                    "code": game.get(code_key, str(tid)),
                }
    return list(teams.values())

def fetch_game(game_id):
    return api_get({"feed": "gc", "tab": "gamesummary", "game_id": game_id})["GC"]["Gamesummary"]


# ── Result type ────────────────────────────────────────────────────────────────
def derive_result_type(meta: dict):
    shootout = str(meta.get("shootout", "0")) == "1"
    period   = int(meta.get("period", 3))
    if shootout:
        return "SO", 1
    elif period > 3:
        return "OT", period - 3
    return "REG", 0


# ── Loaders ────────────────────────────────────────────────────────────────────
def upsert(session, model_class, pk_col: str, pk_val, **kwargs):
    """Simple upsert: merge if exists, insert if not."""
    obj = session.get(model_class, pk_val)
    if obj:
        for k, v in kwargs.items():
            setattr(obj, k, v)
    else:
        obj = model_class(**{pk_col: pk_val, **kwargs})
        session.add(obj)
    return obj


def load_teams(season_id, session):
    teams = fetch_teams(season_id)
    for t in teams:
        upsert(session, Team, "team_id", int(t["id"]),
               team_name=t["name"],
               team_code=t.get("code", t.get("abbreviation", "")),
               season_id=season_id)
    session.commit()
    print(f"  {len(teams)} teams loaded")


def load_game(game_id: int, session, resume: bool = False) -> bool:
    if resume and session.get(Game, game_id):
        print(f"  Game {game_id} already in DB — skipping")
        return True

    try:
        gs   = fetch_game(game_id)
        meta = gs["meta"]

        if str(meta.get("final", "0")) != "1":
            print(f"  Game {game_id} not final — skipping")
            return True

        result_type, ot_periods = derive_result_type(meta)
        game_date = datetime.strptime(meta["date_played"], "%Y-%m-%d").date()

        upsert(session, Game, "game_id", int(meta["id"]),
               season_id        = int(meta["season_id"]),
               date             = game_date,
               home_team_id     = int(meta["home_team"]),
               away_team_id     = int(meta["visiting_team"]),
               home_score       = int(meta["home_goal_count"]),
               away_score       = int(meta["visiting_goal_count"]),
               game_status      = "final",
               result_type      = result_type,
               overtime_periods = ot_periods,
               attendance       = int(meta["attendance"]) if meta.get("attendance") else None,
               venue            = None)

        # Skater stats
        for side, team_key in (("home_team_lineup", "home_team"),
                               ("visitor_team_lineup", "visiting_team")):
            team_id = int(meta[team_key])
            for p in gs.get(side, {}).get("players", []):
                pid = int(p["player_id"])
                upsert(session, Player, "player_id", pid,
                       first_name    = p["first_name"],
                       last_name     = p["last_name"],
                       position      = p.get("position_str", ""),
                       jersey_number = int(p["jersey_number"]) if p.get("jersey_number") else None)

                # Delete then re-insert to avoid duplicates on re-run
                session.query(PlayerGameStats).filter_by(
                    game_id=int(meta["id"]), player_id=pid, team_id=team_id).delete()

                goals   = int(p.get("goals", 0))
                assists = int(p.get("assists", 0))
                # TOI — field name varies by API version; try known candidates
                toi_raw = (p.get("toi") or p.get("time_on_ice") or
                           p.get("shift_time") or p.get("timeOnIce") or
                           p.get("shiftTime"))
                toi_sec = None
                if toi_raw is not None:
                    try:
                        toi_sec = int(toi_raw)  # seconds int
                    except (ValueError, TypeError):
                        try:
                            parts = str(toi_raw).split(":")
                            if len(parts) == 2:
                                toi_sec = int(parts[0]) * 60 + int(parts[1])
                        except (ValueError, TypeError):
                            pass

                session.add(PlayerGameStats(
                    game_id=int(meta["id"]), player_id=pid, team_id=team_id,
                    goals=goals, assists=assists, points=goals + assists,
                    shots=int(p.get("shots", 0)),
                    plus_minus=int(p.get("plus_minus", 0)),
                    pim=int(p.get("pim", 0)),
                    toi_seconds=toi_sec))

        # Goalie stats
        for side, team_key in (("home", "home_team"), ("visitor", "visiting_team")):
            team_id = int(meta[team_key])
            for g in gs.get("goalies", {}).get(side, []):
                pid = int(g["player_id"])
                upsert(session, Player, "player_id", pid,
                       first_name=g["first_name"], last_name=g["last_name"],
                       position="G", jersey_number=None)

                shots_against = int(g.get("shots_against", 0))
                saves         = int(g.get("saves", 0))
                goals_against = int(g.get("goals_against", 0))
                save_pct      = saves / shots_against if shots_against > 0 else None

                win = str(g.get("win", "0")) == "1"
                sol = str(g.get("shootout_loss", "0")) == "1"
                otl = str(g.get("ot_loss", "0")) == "1"
                los = str(g.get("loss", "0")) == "1"
                decision = "W" if win else "SOL" if sol else "OTL" if otl else "L" if los else None

                session.query(GoalieGameStats).filter_by(
                    game_id=int(meta["id"]), player_id=pid, team_id=team_id).delete()

                session.add(GoalieGameStats(
                    game_id=int(meta["id"]), player_id=pid, team_id=team_id,
                    shots_against=shots_against, saves=saves,
                    goals_against=goals_against, save_percentage=save_pct,
                    minutes_played=int(g.get("secs", 0)),  # stored as seconds
                    decision=decision))

        # Update avg_toi_seconds for all players in this game
        session.execute(text("""
            UPDATE players p
            JOIN (
                SELECT s.player_id, ROUND(AVG(s.toi_seconds)) AS avg_toi
                FROM player_game_stats s
                JOIN games g ON g.game_id = s.game_id
                WHERE g.season_id = :sid
                  AND g.game_status = 'final'
                  AND s.toi_seconds IS NOT NULL
                  AND s.player_id IN (
                      SELECT player_id FROM player_game_stats
                      WHERE game_id = :gid
                  )
                GROUP BY s.player_id
            ) agg ON agg.player_id = p.player_id
            SET p.avg_toi_seconds = agg.avg_toi
        """), {"sid": SEASON_ID, "gid": int(meta["id"])})

        session.commit()
        return True

    except Exception as e:
        session.rollback()
        print(f"  Error loading game {game_id}: {e}")
        import traceback; traceback.print_exc()
        return False


# ── Main backfill ──────────────────────────────────────────────────────────────
def backfill(season_id, limit=None, resume=False):
    session = Session()
    print(f"\nPWHL Backfill — Season {season_id}")
    print("=" * 50)

    print("\n[1/3] Loading teams...")
    load_teams(season_id, session)

    print("\n[2/3] Fetching schedule...")
    schedule  = fetch_schedule(season_id)
    completed = [g for g in schedule
                 if str(g.get("game_status", "")).lower() == "final"
                 or str(g.get("status", "")) == "4"
                 or str(g.get("final", "0")) == "1"]
    print(f"  {len(completed)} completed games out of {len(schedule)} scheduled")

    if limit:
        completed = completed[:limit]
        print(f"  Limiting to {limit} games")

    print(f"\n[3/3] Loading {len(completed)} games...")
    ok_count = fail_count = 0
    for i, game in enumerate(completed, 1):
        gid = int(game["id"])
        print(f"  [{i:3d}/{len(completed)}] Game {gid}...", end=" ", flush=True)
        if load_game(gid, session, resume=resume):
            ok_count += 1
            print("OK")
        else:
            fail_count += 1
            print("FAILED")
        time.sleep(RATE_LIMIT)

    session.close()
    print(f"\nDone: {ok_count} loaded, {fail_count} failed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--game",   type=int)
    parser.add_argument("--limit",  type=int)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    if args.game:
        session = Session()
        load_teams(SEASON_ID, session)
        print(f"\nLoading game {args.game}...")
        ok = load_game(args.game, session)
        session.close()
        print("Done" if ok else "Failed")
    else:
        backfill(SEASON_ID, limit=args.limit, resume=args.resume)
