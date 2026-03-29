"""
clinch.py — PWHL playoff clinch calculator.

Determines which teams have mathematically clinched a playoff spot based on
current points and maximum achievable points for all other teams.

Usage:
    from pwhl_btn.analytics.clinch import check_clinched, get_clinched_teams

    # Pure logic (no DB):
    clinched = check_clinched(teams_dict)

    # With DB:
    clinched = get_clinched_teams()          # {team_id: bool}
"""
from __future__ import annotations

PLAYOFF_SPOTS = 4


def check_clinched(teams: dict, playoff_spots: int = PLAYOFF_SPOTS) -> dict[int, bool]:
    """
    Determine which teams have mathematically clinched a playoff spot.

    Args:
        teams: dict of team_id -> {
            "pts":              int,
            "games_remaining":  int,
            "team_code":        str,
        }
        playoff_spots: number of playoff berths (default 4 for PWHL).

    Returns:
        dict of team_id -> bool  (True = clinched)

    A team is clinched when at least (total_teams - playoff_spots) other
    teams can no longer reach that team's current point total regardless
    of how their remaining games play out.
    """
    total_teams     = len(teams)
    must_eliminate  = total_teams - playoff_spots   # teams that must be eliminated

    clinched: dict[int, bool] = {}
    for tid, team in teams.items():
        my_pts = team["pts"]

        eliminated_count = 0
        for oid, other in teams.items():
            if oid == tid:
                continue
            max_other = other["pts"] + (other["games_remaining"] * 3)
            if max_other < my_pts:
                eliminated_count += 1

        clinched[tid] = eliminated_count >= must_eliminate

    return clinched


def check_eliminated(teams: dict, playoff_spots: int = PLAYOFF_SPOTS) -> dict[int, bool]:
    """
    Determine which teams have been mathematically eliminated from the playoffs.

    Args:
        teams: same dict format as check_clinched()
        playoff_spots: number of playoff berths (default 4 for PWHL).

    Returns:
        dict of team_id -> bool  (True = eliminated)

    A team is eliminated when at least playoff_spots other teams already have
    more points than the team can possibly reach (current pts + games_remaining * 2).
    """
    eliminated: dict[int, bool] = {}
    for tid, team in teams.items():
        max_pts = team["pts"] + (team["games_remaining"] * 3)
        ahead_count = sum(
            1 for oid, other in teams.items()
            if oid != tid and other["pts"] > max_pts
        )
        eliminated[tid] = ahead_count >= playoff_spots
    return eliminated


def get_clinched_teams(season_id: int = 8) -> dict[int, bool]:
    """
    Query the DB for current standings and return clinch status per team.

    Returns:
        dict of team_id -> bool  (True = clinched)
    """
    from pwhl_btn.db.db_queries import get_clinch_data
    teams = get_clinch_data(season_id)
    return check_clinched(teams)


def get_newly_clinched_teams(season_id: int = 8, days: int = 1) -> list[int]:
    """
    Returns team_ids that clinched within the last `days` days.

    Compares current clinch status against standings as-of `days` days ago.
    A team appears in the result only if they are clinched now but were NOT
    clinched before the games played in that window.
    """
    from datetime import date, timedelta
    from pwhl_btn.db.db_queries import get_clinch_data

    cutoff   = date.today() - timedelta(days=days)
    current  = get_clinch_data(season_id)
    previous = get_clinch_data(season_id, before_date=cutoff)

    now_clinched  = check_clinched(current)
    then_clinched = check_clinched(previous)

    return [tid for tid, is_clinched in now_clinched.items()
            if is_clinched and not then_clinched.get(tid, False)]


def clinched_team_codes(season_id: int = 8) -> set[str]:
    """Convenience: return set of team_code strings for all clinched teams."""
    from pwhl_btn.db.db_queries import get_clinch_data
    teams = get_clinch_data(season_id)
    result = check_clinched(teams)
    return {teams[tid]["team_code"] for tid, clinched in result.items() if clinched}


if __name__ == "__main__":
    from pwhl_btn.db.db_queries import get_clinch_data

    teams    = get_clinch_data()
    clinched = check_clinched(teams)
    elim     = check_eliminated(teams)

    sorted_teams = sorted(teams.items(), key=lambda x: -x[1]["pts"])

    print(f"\n── PWHL Playoff Clinch Check ────────────────────────────────")
    print(f"  {'#':<3} {'Team':<8} {'PTS':>4}  {'GP Left':>7}  {'Max(×3)':>7}  Status")
    print(f"  {'─'*3} {'─'*8} {'─'*4}  {'─'*7}  {'─'*7}  {'─'*12}")
    for rank, (tid, info) in enumerate(sorted_teams, 1):
        max_pts = info["pts"] + info["games_remaining"] * 3
        if clinched[tid]:
            status = "CLINCHED"
        elif elim[tid]:
            status = "ELIMINATED"
        else:
            status = "in play"
        print(f"  {rank:<3} {info['team_code']:<8} {info['pts']:>4}  {info['games_remaining']:>7}  {max_pts:>7}  {status}")

    n_clinched = sum(clinched.values())
    n_elim     = sum(elim.values())
    print(f"\n  Clinched: {n_clinched} / {len(teams)}   Eliminated: {n_elim} / {len(teams)}\n")
