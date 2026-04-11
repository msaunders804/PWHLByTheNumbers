"""
nhl/market_strength.py — NHL market strength scoring for expansion candidates.

Composite score (0-10) derived from three API-fetchable signals:

  avg_points_pct   (40%) — average points percentage over last 3 seasons.
                           Points % = pts / (gp * 2). Normalised across
                           candidates. Measures sustained on-ice quality,
                           which directly drives gate revenue.

  home_win_pct     (35%) — home W / home GP over last 3 seasons.
                           Home performance drives season-ticket renewals
                           and walk-up sales more than road record.

  playoff_rate     (25%) — playoff appearances / seasons in last 5 years.
                           Playoff hockey = sold-out buildings. Strong
                           proxy for fanbase intensity even in down years.

Hardcoded supplement (stored in data/nhl/market_strength.json):
  avg_home_attendance  — 3-season average home attendance per game.
                         Source: Hockey Reference. Updated manually per season.
                         Used as a display/reference figure, NOT in the score
                         (since the API can't provide it).
"""

from __future__ import annotations
from pwhl_btn.nhl.api import fetch_franchise_seasons, fetch_franchise_playoff_seasons

# Expansion candidate: city -> NHL team_id (mostRecentTeamId from franchise endpoint)
EXPANSION_CANDIDATES: dict[str, int] = {
    "Denver":     21,   # Colorado Avalanche
    "Detroit":    17,   # Detroit Red Wings
    "Calgary":    20,   # Calgary Flames
    "Washington": 15,   # Washington Capitals
    "Chicago":    16,   # Chicago Blackhawks
}

SEASONS_FOR_SCORE    = 3
SEASONS_FOR_PLAYOFFS = 5


def _compute_raw(team_id: int) -> dict:
    reg_seasons     = fetch_franchise_seasons(team_id, num_seasons=SEASONS_FOR_SCORE)
    playoff_seasons = fetch_franchise_playoff_seasons(team_id, num_seasons=SEASONS_FOR_PLAYOFFS)

    # Points percentage over last N regular seasons
    pts_pcts = []
    home_win_pcts = []
    for s in reg_seasons[:SEASONS_FOR_SCORE]:
        gp  = s.get("gamesPlayed") or 0
        pts = s.get("points")      or 0
        if gp:
            pts_pcts.append(pts / (gp * 2))

        home_gp   = (s.get("homeWins") or 0) + (s.get("homeLosses") or 0) + (s.get("homeOvertimeLosses") or 0)
        home_wins = s.get("homeWins") or 0
        if home_gp:
            home_win_pcts.append(home_wins / home_gp)

    avg_pts_pct  = sum(pts_pcts)      / len(pts_pcts)      if pts_pcts      else 0.0
    avg_home_win = sum(home_win_pcts) / len(home_win_pcts) if home_win_pcts else 0.0

    # Playoff rate: appearances in last N seasons
    playoff_season_ids = {s.get("seasonId") for s in playoff_seasons}
    reg_season_ids     = {s.get("seasonId") for s in fetch_franchise_seasons(team_id, num_seasons=SEASONS_FOR_PLAYOFFS)}
    playoff_rate       = (len(playoff_season_ids & reg_season_ids) / SEASONS_FOR_PLAYOFFS
                          if reg_season_ids else 0.0)

    return {
        "avg_pts_pct":   round(avg_pts_pct,  4),
        "avg_home_win":  round(avg_home_win, 4),
        "playoff_rate":  round(playoff_rate, 4),
        "seasons_used":  len(reg_seasons),
    }


def _normalize(values: dict[str, float]) -> dict[str, float]:
    """Min-max normalize a dict of {key: value} to 0-10 scale."""
    if not values:
        return values
    lo  = min(values.values())
    hi  = max(values.values())
    rng = hi - lo or 1.0
    return {k: round((v - lo) / rng * 10, 3) for k, v in values.items()}


def compute_market_scores() -> dict[str, dict]:
    """
    Fetches NHL API data for all expansion candidates and returns
    a dict keyed by city with raw metrics, normalized pillar scores,
    and a weighted composite market_strength_score (0-10).
    """
    raw: dict[str, dict] = {}
    for city, team_id in EXPANSION_CANDIDATES.items():
        print(f"  Fetching NHL data for {city} (team_id={team_id})...")
        raw[city] = {"team_id": team_id, **_compute_raw(team_id)}

    # Normalize each pillar across candidates
    norm_pts      = _normalize({c: raw[c]["avg_pts_pct"]  for c in raw})
    norm_home_win = _normalize({c: raw[c]["avg_home_win"] for c in raw})
    norm_playoff  = _normalize({c: raw[c]["playoff_rate"] for c in raw})

    results = {}
    for city in raw:
        composite = round(
            norm_pts[city]      * 0.40 +
            norm_home_win[city] * 0.35 +
            norm_playoff[city]  * 0.25,
            3
        )
        results[city] = {
            **raw[city],
            "norm_pts_pct":   norm_pts[city],
            "norm_home_win":  norm_home_win[city],
            "norm_playoff":   norm_playoff[city],
            "market_strength_score": composite,
        }

    return results
