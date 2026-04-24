"""
expansion.py — PWHL Expansion City Scorecard

"I ran the numbers on where PWHL should expand — and the answer might surprise you."

Scores candidate cities across 5 weighted metrics:
  1. NHL market depth        (25%) — computed from NHL API via nhl/market_strength.py,
                                     cached in data/nhl/market_strength.json.
                                     Falls back to expansion_cities.json score if cache
                                     hasn't been populated yet.
  2. Takeover Tour attendance (35%) — pulled live from DB, normalized 0-10
  3. Women's sports viability (20%) — researched, stored in expansion_cities.json
  4. Arena fit               (10%) — researched, stored in expansion_cities.json
  5. Geographic balance      (10%) — researched, stored in expansion_cities.json

Tour attendance is normalized: best avg attendance in the dataset = 10.0.
Cities with multiple tour games get the average; single-game cities noted.

Refresh NHL market data:
    python -m pwhl_btn.jobs.fetch_nhl_market_data
"""

from __future__ import annotations
import json
from pathlib import Path
from sqlalchemy import text
from pwhl_btn.db.db_config import get_engine

SEASON_ID       = 8
DATA_FILE       = Path(__file__).resolve().parents[3] / "data" / "expansion_cities.json"
NHL_MARKET_FILE = Path(__file__).resolve().parents[3] / "data" / "nhl" / "market_strength.json"


def _load_nhl_market_scores() -> dict[str, float]:
    """
    Returns {city: market_strength_score (0-10)} from the NHL cache file.
    Returns empty dict if the file hasn't been populated yet (fetch job not run).
    """
    if not NHL_MARKET_FILE.exists():
        return {}
    cache = json.loads(NHL_MARKET_FILE.read_text(encoding="utf-8"))
    scores = {}
    for city, data in cache.get("candidates", {}).items():
        api = data.get("api_derived", {})
        if api.get("market_strength_score") is not None:
            scores[city] = api["market_strength_score"]
    return scores


# ── Tour attendance from DB ────────────────────────────────────────────────────

def _get_tour_attendance(conn, home_venues: list[str], season_id: int) -> dict[str, dict]:
    """
    Returns {venue: {avg_att, total_att, game_count}} for all non-home venues,
    aggregated across all seasons with venue data (not just the current season).
    """
    rows = conn.execute(text("""
        SELECT g.venue,
               COUNT(*)           AS game_count,
               SUM(g.attendance)  AS total_att
        FROM games g
        WHERE g.game_status = 'final'
          AND g.venue       IS NOT NULL
          AND g.attendance  IS NOT NULL
        GROUP BY g.venue
    """)).fetchall()

    return {
        r.venue: {
            "avg_att":    round(int(r.total_att or 0) / int(r.game_count)) if r.game_count else 0,
            "total_att":  int(r.total_att or 0),
            "game_count": int(r.game_count),
        }
        for r in rows
        if r.venue not in home_venues
    }


def _normalize_attendance(cities: list[dict]) -> dict[str, float]:
    """Normalize tour attendance to 0-10 scale. Best = 10."""
    avgs = {c["city"]: c.get("tour_avg_att", 0) for c in cities}
    max_att = max(avgs.values()) if avgs else 1
    return {city: round((att / max_att) * 10, 2) for city, att in avgs.items()}


# ── Scoring engine ─────────────────────────────────────────────────────────────

def score_cities(season_id: int = SEASON_ID) -> list[dict]:
    """
    Returns candidate cities ranked by weighted composite score.
    Each dict includes raw metrics, normalized scores, weighted total, and narrative.
    """
    config = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    weights = config["weights"]
    home_venues = config["existing_pwhl_home_venues"]
    candidates  = config["candidates"]

    engine = get_engine(pool_pre_ping=True)
    with engine.connect() as conn:
        tour_data = _get_tour_attendance(conn, home_venues, season_id)

    # Load NHL market scores from cache (populated by fetch_nhl_market_data job)
    nhl_scores = _load_nhl_market_scores()
    if nhl_scores:
        # Normalize cached scores to 0-10 relative to this candidate set
        max_nhl = max(nhl_scores.values()) or 1
        nhl_scores = {c: round((s / max_nhl) * 10, 3) for c, s in nhl_scores.items()}

    # Attach live tour data to each candidate
    for c in candidates:
        venue = c.get("tour_venue", "")
        td    = tour_data.get(venue, {})
        c["tour_avg_att"]    = td.get("avg_att",    0)
        c["tour_total_att"]  = td.get("total_att",  0)
        c["tour_game_count"] = td.get("game_count", 0)

    # Normalize attendance to 0-10
    att_scores = _normalize_attendance(candidates)

    results = []
    for c in candidates:
        att_score = att_scores.get(c["city"], 0)

        # Use live NHL market score if available, fall back to hardcoded value
        nhl_market_score = nhl_scores.get(c["city"], c["nhl_market_score"])

        pillar_scores = {
            "nhl_market":      nhl_market_score,
            "tour_attendance": att_score,
            "womens_sports":   c["womens_sports_score"],
            "arena_fit":       c["arena_fit_score"],
            "geo_balance":     c["geo_balance_score"],
        }

        composite = round(
            pillar_scores["nhl_market"]      * weights["nhl_market"]     +
            pillar_scores["tour_attendance"] * weights["tour_attendance"] +
            pillar_scores["womens_sports"]   * weights["womens_sports"]   +
            pillar_scores["arena_fit"]       * weights["arena_fit"]       +
            pillar_scores["geo_balance"]     * weights["geo_balance"],
            3
        )

        results.append({
            "city":              c["city"],
            "state_province":    c["state_province"],
            "country":           c["country"],
            "nhl_team":          c["nhl_team"],
            "tour_venue":        c["tour_venue"],
            "tour_avg_att":      c["tour_avg_att"],
            "tour_total_att":    c["tour_total_att"],
            "tour_game_count":   c["tour_game_count"],
            "nhl_market_score":  nhl_market_score,
            "nhl_market_source": "api" if c["city"] in nhl_scores else "hardcoded",
            "nhl_market_notes":  c["nhl_market_notes"],
            "womens_sports_score": c["womens_sports_score"],
            "womens_sports_notes": c["womens_sports_notes"],
            "arena_fit_score":   c["arena_fit_score"],
            "arena_fit_notes":   c["arena_fit_notes"],
            "geo_balance_score": c["geo_balance_score"],
            "geo_balance_notes": c["geo_balance_notes"],
            "pillar_scores":     pillar_scores,
            "composite_score":   composite,
            "narrative_hook":    c.get("narrative_hook", ""),
        })

    results.sort(key=lambda x: x["composite_score"], reverse=True)
    for i, r in enumerate(results, start=1):
        r["rank"] = i

    return results
