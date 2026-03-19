"""
records.py — Season record definitions and recent-break detection.

A "record" is always computed live from the DB — no separate storage needed
because the DB is already the source of truth.  A record is broken when the
season-best value for a stat was achieved within the look-back window.

Adding a new record:
  1. Define a fetch_instances() function — returns rows with at least
     (game_id, team_id|None, value, date) ordered by value DESC.
  2. Define a fetch_detail() function (or None) — returns scorer rows for
     slide 2.
  3. Add a RecordDefinition to TRACKED_RECORDS.

Usage:
    from pwhl_btn.analytics.records import check_recent_records
    broken = check_recent_records(days=7)
    for ctx in broken:
        render_slides(ctx)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

from sqlalchemy import create_engine, text

SEASON_ID = 8


def _load_dotenv():
    base = Path(__file__).resolve()
    for env_path in [base.parent / ".env",
                     base.parents[1] / ".env",
                     base.parents[2] / ".env",
                     base.parents[3] / ".env"]:
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, _, v = line.partition("=")
                    k = k.strip(); v = v.strip().strip('"').strip("'")
                    if k and k not in os.environ:
                        os.environ[k] = v
            break

_load_dotenv()


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _fmt_date(d) -> str:
    """Format a date object to 'Mar 18, 2026', stripping leading zeros cross-platform."""
    if not hasattr(d, "strftime"):
        return str(d)
    s = d.strftime("%b {d}, %Y").replace("{d}", str(d.day))
    return s


def _prev_holders_label(holders: list[dict]) -> str:
    teams = [h["team_code"] for h in holders]
    if not teams:
        return "None"
    if len(teams) == 1:
        return teams[0]
    if len(teams) == 2:
        return f"{teams[0]} & {teams[1]}"
    return f"{', '.join(teams[:-1])} & {teams[-1]}"


def _game_result_str(team_code, home_code, home_score, away_score) -> tuple[str, str]:
    """Returns (result_str, opponent_code) from the record team's perspective."""
    if team_code == home_code:
        ts, os_ = home_score, away_score
        opp = "away"
    else:
        ts, os_ = away_score, home_score
        opp = "home"
    suffix = "W" if ts > os_ else "L"
    return f"{ts}-{os_} {suffix}", opp


# ── Record definition ──────────────────────────────────────────────────────────

@dataclass
class RecordDefinition:
    """
    id:              unique slug used in output filenames
    name:            display name on the slides
    value_unit:      e.g. "SKATERS", "GOALS"
    detail_slide:    whether to render slide 2 (scorer breakdown)
    fetch_instances: (conn, season_id) -> list of Row with
                         .game_id, .team_id (or None), .team_code (or None),
                         .value, .date, .home_code, .away_code,
                         .home_score, .away_score, .team_name (optional)
    fetch_detail:    (conn, game_id, team_id|None) -> list of scorer dicts
                     {name, goals, assists, points}  — may be None
    """
    id:               str
    name:             str
    value_unit:       str
    detail_slide:     bool
    fetch_instances:  Callable
    fetch_detail:     Callable | None = None


# ── Record 1: Most skaters with a point — single team ─────────────────────────

def _fetch_skaters_with_point(conn, season_id: int):
    return conn.execute(text("""
        SELECT
            pgs.game_id,
            pgs.team_id,
            t.team_code,
            t.team_name,
            g.date,
            ht.team_code  AS home_code,
            at.team_code  AS away_code,
            g.home_score,
            g.away_score,
            COUNT(DISTINCT pgs.player_id) AS value
        FROM player_game_stats pgs
        JOIN games g  ON g.game_id  = pgs.game_id
        JOIN teams ht ON ht.team_id = g.home_team_id
        JOIN teams at ON at.team_id = g.away_team_id
        JOIN teams t  ON t.team_id  = pgs.team_id
        WHERE g.season_id = :sid
          AND g.game_status = 'Final'
          AND (pgs.goals > 0 OR pgs.assists > 0)
        GROUP BY pgs.game_id, pgs.team_id, t.team_code, t.team_name,
                 g.date, ht.team_code, at.team_code, g.home_score, g.away_score
        ORDER BY value DESC
    """), {"sid": season_id}).fetchall()


def _fetch_skaters_detail(conn, game_id: int, team_id: int):
    rows = conn.execute(text("""
        SELECT CONCAT(p.first_name, ' ', p.last_name) AS name,
               pgs.goals, pgs.assists, pgs.points
        FROM player_game_stats pgs
        JOIN players p ON p.player_id = pgs.player_id
        WHERE pgs.game_id = :gid
          AND pgs.team_id = :tid
          AND (pgs.goals > 0 OR pgs.assists > 0)
        ORDER BY pgs.points DESC, pgs.goals DESC
    """), {"gid": game_id, "tid": team_id}).fetchall()
    return [{"name": r.name, "goals": r.goals, "assists": r.assists, "points": r.points}
            for r in rows]


# ── Record 2: Highest goal differential ───────────────────────────────────────

def _fetch_goal_diff(conn, season_id: int):
    return conn.execute(text("""
        SELECT
            g.game_id,
            NULL            AS team_id,
            ht.team_code    AS team_code,
            ht.team_name    AS team_name,
            g.date,
            ht.team_code    AS home_code,
            at.team_code    AS away_code,
            g.home_score,
            g.away_score,
            ABS(g.home_score - g.away_score) AS value
        FROM games g
        JOIN teams ht ON ht.team_id = g.home_team_id
        JOIN teams at ON at.team_id = g.away_team_id
        WHERE g.season_id = :sid
          AND g.game_status = 'Final'
        ORDER BY value DESC
    """), {"sid": season_id}).fetchall()


def _fetch_goal_diff_detail(conn, game_id: int, team_id):
    """All scorers from both teams, ordered by points."""
    rows = conn.execute(text("""
        SELECT CONCAT(p.first_name, ' ', p.last_name) AS name,
               t.team_code,
               pgs.goals, pgs.assists, pgs.points
        FROM player_game_stats pgs
        JOIN players p ON p.player_id = pgs.player_id
        JOIN teams  t  ON t.team_id   = pgs.team_id
        WHERE pgs.game_id = :gid
          AND (pgs.goals > 0 OR pgs.assists > 0)
        ORDER BY pgs.points DESC, pgs.goals DESC
    """), {"gid": game_id}).fetchall()
    return [{"name": r.name, "goals": r.goals, "assists": r.assists, "points": r.points}
            for r in rows]


# ── Registry ───────────────────────────────────────────────────────────────────

TRACKED_RECORDS: list[RecordDefinition] = [
    RecordDefinition(
        id            = "skaters_with_point_single_team",
        name          = "MOST SKATERS WITH A POINT - SINGLE TEAM",
        value_unit    = "SKATERS",
        detail_slide  = True,
        fetch_instances = _fetch_skaters_with_point,
        fetch_detail    = _fetch_skaters_detail,
    ),
    RecordDefinition(
        id            = "goal_differential",
        name          = "HIGHEST GOAL DIFFERENTIAL",
        value_unit    = "GOALS",
        detail_slide  = True,
        fetch_instances = _fetch_goal_diff,
        fetch_detail    = _fetch_goal_diff_detail,
    ),
]


# ── Core checker ──────────────────────────────────────────────────────────────

def check_recent_records(days: int = 7) -> list[dict]:
    """
    Returns a list of render contexts for every tracked record that was
    broken or tied-as-best within the last `days` days.

    Each context dict is ready to pass directly to render_slides().
    """
    from pwhl_btn.db.db_config import get_db_url
    from pwhl_btn.db.db_queries import _logo_uri, _pwhl_logo_uri, _player_photo_uri

    engine  = create_engine(get_db_url(), pool_pre_ping=True)
    cutoff  = date.today() - timedelta(days=days)
    results = []

    with engine.connect() as conn:
        for rec in TRACKED_RECORDS:
            instances = rec.fetch_instances(conn, SEASON_ID)
            if not instances:
                continue

            best_value = instances[0].value

            # Games that achieved the best value AND are within the window
            recent_best = [i for i in instances
                           if i.value == best_value and i.date >= cutoff]
            if not recent_best:
                continue

            # Previous record = best value among games NOT in the recent batch.
            # Filtering by game_id+team_id (not by value) means a tie is caught:
            # if another game already holds the same value it becomes a prev_holder
            # with prev_value == best_value, and is_tie is set True.
            recent_keys    = {(i.game_id, getattr(i, "team_id", None)) for i in recent_best}
            prev_instances = [i for i in instances
                              if (i.game_id, getattr(i, "team_id", None)) not in recent_keys]
            prev_value     = prev_instances[0].value if prev_instances else 0
            is_tie         = (prev_value == best_value)

            # Build previous holders list (all games that held the old record)
            prev_holders = []
            for pi in prev_instances:
                if pi.value < prev_value:
                    break
                if pi.team_id is not None:
                    opp = pi.away_code if pi.team_code == pi.home_code else pi.home_code
                    ts  = pi.home_score if pi.team_code == pi.home_code else pi.away_score
                    os_ = pi.away_score if pi.team_code == pi.home_code else pi.home_score
                else:
                    # Game-level record (e.g. goal diff) — winning team is the holder
                    if pi.home_score > pi.away_score:
                        opp = pi.away_code
                        ts, os_ = pi.home_score, pi.away_score
                    else:
                        opp = pi.home_code
                        ts, os_ = pi.away_score, pi.home_score
                prev_holders.append({
                    "team_code": pi.team_code,
                    "logo":      _logo_uri(pi.team_code),
                    "game_date": _fmt_date(pi.date),
                    "opponent":  f"vs {opp}",
                    "score":     f"{ts}-{os_}",
                })

            # Build one context per record-breaking game (usually just one)
            for inst in recent_best:
                # Determine opponent + result from the record team's perspective
                if inst.team_id is not None:
                    # Team-level record
                    game_result, opp_code = _game_result_str(
                        inst.team_code, inst.home_code,
                        inst.home_score, inst.away_score
                    )
                    opp_code = (inst.away_code if inst.team_code == inst.home_code
                                else inst.home_code)
                    team_name = getattr(inst, "team_name", inst.team_code)
                else:
                    # Game-level record — attribute to the winning team
                    if inst.home_score > inst.away_score:
                        team_name = inst.home_code
                        opp_code  = inst.away_code
                        game_result = f"{inst.home_score}-{inst.away_score} W"
                    else:
                        team_name = inst.away_code
                        opp_code  = inst.home_code
                        game_result = f"{inst.away_score}-{inst.home_score} W"

                # Scorers for slide 2
                scorers = []
                if rec.detail_slide and rec.fetch_detail:
                    scorers = rec.fetch_detail(conn, inst.game_id, inst.team_id)

                # Optional featured player photo (top scorer)
                featured_name  = scorers[0]["name"] if scorers else None
                featured_photo = _player_photo_uri(featured_name) if featured_name else None

                results.append({
                    # Record identity
                    "record_id":         rec.id,
                    "record_name":       rec.name,
                    "new_value":         inst.value,
                    "new_value_unit":    rec.value_unit,
                    # New record holder
                    "new_team_code":     inst.team_code,
                    "new_team_name":     team_name,
                    "new_team_logo":     _logo_uri(inst.team_code),
                    "new_game_result":   game_result,
                    "new_game_opponent": opp_code,
                    "new_game_date":     _fmt_date(inst.date),
                    # Optional player photo
                    "player_photo":         featured_photo,
                    "featured_player_name": featured_name,
                    # Previous record
                    "prev_value":         prev_value,
                    "prev_holders":       prev_holders,
                    "prev_holders_label": _prev_holders_label(prev_holders),
                    # Record status
                    "is_tie":             is_tie,
                    # Slide 2
                    "scorers":            scorers,
                    "include_detail_slide": rec.detail_slide,
                    # Meta
                    "season":    SEASON_ID,
                    "pwhl_logo": _pwhl_logo_uri(),
                })

    return results
