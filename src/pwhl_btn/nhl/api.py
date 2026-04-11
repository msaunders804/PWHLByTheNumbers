"""
nhl/api.py — NHL API client for market strength data.

Sources:
  records.nhl.com/site/api/franchise-season-results
      Regular-season results (W/L/OTL/points/home record) per team per season.

  api-web.nhle.com/v1/standings/{date}
      Current standings snapshot — used to confirm team IDs.

NOTE: The NHL public API does not expose per-team attendance figures.
      Attendance data in data/nhl/market_strength.json is hardcoded from
      Hockey Reference (https://www.hockey-reference.com/leagues/NHL_2025.html)
      and must be updated manually each season.
"""

from __future__ import annotations
import requests
from time import sleep

NHL_RECORDS_BASE = "https://records.nhl.com/site/api"
NHL_WEB_BASE     = "https://api-web.nhle.com/v1"
RATE_LIMIT       = 0.3   # seconds between requests


def _get(url: str, params: dict | None = None) -> dict:
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_franchise_seasons(team_id: int, num_seasons: int = 5) -> list[dict]:
    """
    Returns the last `num_seasons` regular-season records for a team.
    gameTypeId=2 = regular season.
    """
    url  = f"{NHL_RECORDS_BASE}/franchise-season-results"
    expr = f"teamId={team_id} and gameTypeId=2"
    data = _get(url, params={
        "cayenneExp": expr,
        "sort":       "seasonId",
        "dir":        "DESC",
        "limit":      num_seasons,
    })
    sleep(RATE_LIMIT)
    return data.get("data", [])


def fetch_franchise_playoff_seasons(team_id: int, num_seasons: int = 5) -> list[dict]:
    """
    Returns playoff appearances (gameTypeId=3) for the last `num_seasons` seasons.
    A result existing = team made the playoffs that year.
    """
    url  = f"{NHL_RECORDS_BASE}/franchise-season-results"
    expr = f"teamId={team_id} and gameTypeId=3"
    data = _get(url, params={
        "cayenneExp": expr,
        "sort":       "seasonId",
        "dir":        "DESC",
        "limit":      num_seasons,
    })
    sleep(RATE_LIMIT)
    return data.get("data", [])


def fetch_all_franchises() -> list[dict]:
    """Returns all NHL franchises with their mostRecentTeamId."""
    data = _get(f"{NHL_RECORDS_BASE}/franchise")
    sleep(RATE_LIMIT)
    return data.get("data", [])
