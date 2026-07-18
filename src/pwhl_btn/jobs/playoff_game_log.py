"""
playoff_game_log.py — Print per-game stats for all season 9 playoff games.
Usage: python -m pwhl_btn.jobs.playoff_game_log
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import text
from sqlalchemy.orm import Session

from pwhl_btn.db.db_config import get_engine

SEASON_ID = 9

engine = get_engine()


def _games(session) -> list[dict]:
    rows = session.execute(text("""
        SELECT g.game_id, g.date, g.home_score, g.away_score, g.result_type,
               ht.team_code AS home_code, ht.team_name AS home_name,
               at.team_code AS away_code, at.team_name AS away_name
        FROM games g
        JOIN teams ht ON ht.team_id = g.home_team_id AND ht.season_id = :sid
        JOIN teams at ON at.team_id = g.away_team_id AND at.season_id = :sid
        WHERE g.season_id = :sid AND g.game_status = 'final'
        ORDER BY g.date ASC, g.game_id ASC
    """), {"sid": SEASON_ID}).fetchall()
    return [dict(r._mapping) for r in rows]


def _scorers(session, game_id: int) -> list[dict]:
    rows = session.execute(text("""
        SELECT p.first_name, p.last_name, t.team_code,
               pgs.goals, pgs.assists, pgs.pim
        FROM player_game_stats pgs
        JOIN players p ON p.player_id = pgs.player_id
        JOIN teams   t ON t.team_id   = pgs.team_id AND t.season_id = :sid
        WHERE pgs.game_id = :gid
          AND (pgs.goals > 0 OR pgs.assists > 0 OR pgs.pim > 0)
        ORDER BY t.team_code, pgs.goals DESC, pgs.assists DESC
    """), {"sid": SEASON_ID, "gid": game_id}).fetchall()
    return [dict(r._mapping) for r in rows]


def _team_pim(session, game_id: int) -> dict[str, int]:
    rows = session.execute(text("""
        SELECT t.team_code, SUM(pgs.pim) AS total_pim
        FROM player_game_stats pgs
        JOIN teams t ON t.team_id = pgs.team_id AND t.season_id = :sid
        WHERE pgs.game_id = :gid
        GROUP BY t.team_code
    """), {"sid": SEASON_ID, "gid": game_id}).fetchall()
    return {r.team_code: int(r.total_pim or 0) for r in rows}


def print_game(game: dict, scorers: list[dict], pim: dict[str, int]) -> None:
    home, away = game["home_code"], game["away_code"]
    hs, as_ = game["home_score"], game["away_score"]
    rt = game["result_type"] or "REG"
    suffix = f" ({rt})" if rt != "REG" else ""

    winner_code = home if hs > as_ else away
    winner_name = game["home_name"] if hs > as_ else game["away_name"]

    date_str = str(game["date"])

    print()
    print("=" * 52)
    print(f"  Game {game['game_id']}  |  {date_str}  |  {away} @ {home}")
    print(f"  FINAL:   {home} {hs}  -  {away} {as_}{suffix}")
    print(f"  WINNER:  {winner_name} ({winner_code})")
    print("-" * 52)

    # Goals
    goal_rows = [(s["team_code"], f"{s['first_name']} {s['last_name']}", s["goals"])
                 for s in scorers if s["goals"] > 0]
    if goal_rows:
        print("  GOALS")
        for team, name, n in goal_rows:
            marker = f" (x{n})" if n > 1 else ""
            print(f"    {team:<4}  {name}{marker}")
    else:
        print("  GOALS     —")

    print()

    # Assists
    assist_rows = [(s["team_code"], f"{s['first_name']} {s['last_name']}", s["assists"])
                   for s in scorers if s["assists"] > 0]
    if assist_rows:
        print("  ASSISTS")
        for team, name, n in assist_rows:
            marker = f" (x{n})" if n > 1 else ""
            print(f"    {team:<4}  {name}{marker}")
    else:
        print("  ASSISTS   —")

    print()

    # Penalty minutes
    print("  PENALTY MINUTES")
    for team in sorted(pim):
        print(f"    {team:<4}  {pim[team]} PIM")

    print("=" * 52)


def run() -> None:
    with Session(engine) as session:
        games = _games(session)
        if not games:
            print(f"No completed playoff games found for season {SEASON_ID}.")
            return

        print(f"\nPWHL Playoffs — Season {SEASON_ID}  ({len(games)} games)")

        for game in games:
            scorers = _scorers(session, game["game_id"])
            pim     = _team_pim(session, game["game_id"])
            print_game(game, scorers, pim)

        print()


if __name__ == "__main__":
    run()
