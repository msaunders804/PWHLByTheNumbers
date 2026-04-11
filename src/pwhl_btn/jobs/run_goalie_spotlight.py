"""
run_goalie_spotlight.py — "The Goalie Carrying Her Team" CLI report.

Identifies the goalie with the strongest case for carrying her team using:
  - Season GSAA
  - Stolen games (wins where defense broke down but she held)
  - High-leverage wins (standings-relevant games where she outperformed)

Usage:
    python -m pwhl_btn.jobs.run_goalie_spotlight              # auto-identify top carrier
    python -m pwhl_btn.jobs.run_goalie_spotlight --all        # full leaderboard only
    python -m pwhl_btn.jobs.run_goalie_spotlight --player 123 # spotlight specific player_id
"""

import argparse

from pwhl_btn.analytics.gsaa import (
    get_season_gsaa,
    get_goalie_game_log,
    get_stolen_games,
    get_high_leverage_wins,
    find_top_carrier,
    SEASON_ID,
)


def _fmt_pct(v) -> str:
    return f".{int(round(float(v or 0), 3) * 1000):03d}"


def _fmt_gsaa(v) -> str:
    return f"{float(v):+.2f}"


def print_leaderboard(rows: list[dict]) -> None:
    print(f"\n  Season GSAA Leaderboard — Season {SEASON_ID}")
    print(f"  {'#':<3}  {'GOALIE':<22}  {'TEAM':<5}  {'GP':>3}  {'SA':>4}  "
          f"{'SV%':>6}  {'GAA':>5}  {'GSAA':>6}  {'W':>3}  {'SO':>3}")
    print("  " + "─" * 72)
    for i, r in enumerate(rows, start=1):
        print(f"  {i:<3}  {r['name']:<22}  {r['team_code']:<5}  {int(r['gp']):>3}  "
              f"{int(r['sa']):>4}  {_fmt_pct(r['sv_pct']):>6}  "
              f"{float(r['gaa'] or 0):>5.2f}  {_fmt_gsaa(r['gsaa']):>6}  "
              f"{int(r['wins']):>3}  {int(r['shutouts']):>3}")
    print()


def print_game_log(game_log: list[dict], name: str) -> None:
    print(f"\n  Game Log — {name}")
    print(f"  {'DATE':<15}  {'OPP':<5}  {'H/A':<4}  {'SA':>3}  {'SV':>3}  "
          f"{'SV%':>6}  {'GSAA':>6}  {'DEC':>4}")
    print("  " + "─" * 58)
    running = 0.0
    for g in game_log:
        running += g["gsaa"]
        dec = g["decision"] or "—"
        if g["result_type"] and g["result_type"] != "REG" and dec in ("W", "L"):
            dec = f"{dec}/{g['result_type']}"
        print(f"  {g['date_str']:<15}  {g['opponent']:<5}  {g['home_away']:<4}  "
              f"{int(g['shots_against']):>3}  {int(g['saves']):>3}  "
              f"{_fmt_pct(g['game_sv_pct']):>6}  {_fmt_gsaa(g['gsaa']):>6}  "
              f"{dec:>6}   (running: {running:+.2f})")
    print()


def print_stolen_games(stolen: list[dict], name: str) -> None:
    if not stolen:
        print(f"\n  Stolen Games — {name}: none found\n")
        return
    print(f"\n  Stolen Games — {name}  "
          f"(W + shots above team avg + SV% above league avg)")
    print(f"  {'DATE':<15}  {'OPP':<5}  {'SA':>3}  {'TEAM AVG SA':>11}  "
          f"{'SV%':>6}  {'GSAA':>6}")
    print("  " + "─" * 58)
    for g in stolen:
        print(f"  {g['date_str']:<15}  {g['opponent']:<5}  "
              f"{int(g['shots_against']):>3}  {g['team_avg_sa']:>11.1f}  "
              f"{_fmt_pct(g['game_sv_pct']):>6}  {_fmt_gsaa(g['gsaa']):>6}")
    print()


def print_leverage_wins(leverage: list[dict], name: str) -> None:
    if not leverage:
        print(f"\n  High-Leverage Wins — {name}: none found\n")
        return
    print(f"\n  High-Leverage Wins — {name}  "
          f"(standings-relevant games, GSAA > 0)")
    print(f"  {'DATE':<15}  {'OPP':<5}  {'GSAA':>6}  "
          f"{'TEAM POS':>9}  {'OPP POS':>8}  {'PT GAP':>7}")
    print("  " + "─" * 62)
    for g in leverage:
        pos      = f"#{g['team_position']} ({g['team_points']}pts)"
        opp_pos  = f"#{g['opp_position']} ({g['opp_points']}pts)" if g['opp_position'] else "—"
        print(f"  {g['date_str']:<15}  {g['opponent']:<5}  "
              f"{_fmt_gsaa(g['gsaa']):>6}  "
              f"{pos:>9}  {opp_pos:>8}  {g['points_gap']:>6}pts")
    print()


def print_spotlight(data: dict) -> None:
    s    = data["season_stats"]
    name = s["name"]

    print("\n" + "=" * 72)
    print(f"  GOALIE SPOTLIGHT: {name}  ({s['team_code']})")
    print(f"  Carrier Score: {data['carrier_score']}  |  "
          f"Season GSAA: {_fmt_gsaa(s['gsaa'])}  |  "
          f"SV%: {_fmt_pct(s['sv_pct'])}  |  "
          f"GAA: {float(s['gaa'] or 0):.2f}")
    print(f"  GP: {s['gp']}  |  Stolen Games: {len(data['stolen_games'])}  |  "
          f"High-Leverage Wins: {len(data['leverage_wins'])}")
    print("=" * 72)

    print_game_log(data["game_log"], name)
    print_stolen_games(data["stolen_games"], name)
    print_leverage_wins(data["leverage_wins"], name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--all",    action="store_true", help="Print full leaderboard only")
    parser.add_argument("--player", type=int,            help="Spotlight a specific player_id")
    args = parser.parse_args()

    print(f"\n  Loading goalie data for Season {SEASON_ID}...")
    leaderboard = get_season_gsaa()

    if not leaderboard:
        print("  No qualified goalies found. Check that goalie_game_stats is populated.")
        return

    print_leaderboard(leaderboard)

    if args.all:
        return

    if args.player:
        match = next((g for g in leaderboard if g["player_id"] == args.player), None)
        if not match:
            print(f"  player_id {args.player} not found in qualified goalies.")
            return
        pid  = args.player
        data = {
            "season_stats":  match,
            "game_log":      get_goalie_game_log(pid),
            "stolen_games":  get_stolen_games(pid),
            "leverage_wins": get_high_leverage_wins(pid),
            "carrier_score": "—",
        }
        print_spotlight(data)
        return

    # Auto-identify the top carrier
    print("  Identifying top carrier...")
    data = find_top_carrier()
    if not data:
        print("  Could not determine top carrier.")
        return
    print_spotlight(data)


if __name__ == "__main__":
    main()
