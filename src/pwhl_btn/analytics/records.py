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

from sqlalchemy import text

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
    names = [h.get("display_name") or h["team_code"] for h in holders]
    if not names:
        return "None"
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} & {names[1]}"
    return f"{', '.join(names[:-1])} & {names[-1]}"


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
    badge_text:       str | None      = None   # overrides default "Record Broken" badge


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


# ── Record 3: Season points leader (highest cumulative points by one player) ───

def _fetch_season_points_leader(conn, season_id: int):
    """
    For each player, returns the game where their cumulative season points
    reached their personal season high. Ordered by that high DESC — so the
    all-time season leader sits at row 0.
    """
    return conn.execute(text("""
        WITH player_season_pts AS (
            SELECT
                s.player_id,
                s.team_id,
                s.game_id,
                SUM(s.points) OVER (
                    PARTITION BY s.player_id
                    ORDER BY g.date, s.game_id
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                ) AS running_total,
                g.date,
                ht.team_code  AS home_code,
                at.team_code  AS away_code,
                g.home_score,
                g.away_score
            FROM player_game_stats s
            JOIN games g  ON g.game_id  = s.game_id
            JOIN teams ht ON ht.team_id = g.home_team_id
            JOIN teams at ON at.team_id = g.away_team_id
            WHERE g.season_id = :sid AND g.game_status = 'Final'
        ),
        player_max AS (
            SELECT player_id, MAX(running_total) AS season_high
            FROM player_season_pts
            GROUP BY player_id
        ),
        peak_game AS (
            SELECT psp.*
            FROM player_season_pts psp
            JOIN player_max pm ON pm.player_id = psp.player_id
                               AND pm.season_high = psp.running_total
        ),
        ranked AS (
            SELECT *,
                   ROW_NUMBER() OVER (PARTITION BY player_id ORDER BY date DESC, game_id DESC) AS rn
            FROM peak_game
        )
        SELECT
            r.game_id,
            r.team_id,
            t.team_code,
            CONCAT(p.first_name, ' ', p.last_name) AS team_name,
            r.date,
            r.home_code,
            r.away_code,
            r.home_score,
            r.away_score,
            r.running_total AS value
        FROM ranked r
        JOIN players p ON p.player_id = r.player_id
        JOIN teams   t ON t.team_id   = r.team_id
        WHERE r.rn = 1
        ORDER BY r.running_total DESC
    """), {"sid": season_id}).fetchall()


def _fetch_season_pts_detail(conn, game_id: int, team_id: int):
    rows = conn.execute(text("""
        SELECT CONCAT(p.first_name, ' ', p.last_name) AS name,
               pgs.goals, pgs.assists, pgs.points
        FROM player_game_stats pgs
        JOIN players p ON p.player_id = pgs.player_id
        WHERE pgs.game_id = :gid AND pgs.team_id = :tid
          AND (pgs.goals > 0 OR pgs.assists > 0)
        ORDER BY pgs.points DESC, pgs.goals DESC
    """), {"gid": game_id, "tid": team_id}).fetchall()
    return [{"name": r.name, "goals": r.goals, "assists": r.assists, "points": r.points}
            for r in rows]


# ── Record 4: Game attendance ──────────────────────────────────────────────────

def _fetch_game_attendance(conn, season_id: int):
    return conn.execute(text("""
        SELECT
            g.game_id,
            g.home_team_id  AS team_id,
            ht.team_code,
            ht.team_name,
            g.date,
            ht.team_code    AS home_code,
            at.team_code    AS away_code,
            g.home_score,
            g.away_score,
            g.attendance    AS value
        FROM games g
        JOIN teams ht ON ht.team_id = g.home_team_id
        JOIN teams at ON at.team_id = g.away_team_id
        WHERE g.season_id  = :sid
          AND g.game_status = 'Final'
          AND g.attendance IS NOT NULL
          AND g.attendance  > 0
        ORDER BY g.attendance DESC
    """), {"sid": season_id}).fetchall()


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
    RecordDefinition(
        id            = "season_points_leader",
        name          = "MOST POINTS IN A SEASON — 2025–26",
        value_unit    = "PTS",
        detail_slide  = False,
        fetch_instances = _fetch_season_points_leader,
        fetch_detail    = None,
        badge_text    = "2025–26 Season Record",
    ),
    RecordDefinition(
        id            = "game_attendance",
        name          = "HIGHEST GAME ATTENDANCE",
        value_unit    = "FANS",
        detail_slide  = False,
        fetch_instances = _fetch_game_attendance,
        fetch_detail    = None,
    ),
]


# ── Core checker ──────────────────────────────────────────────────────────────

def check_recent_records(days: int = 7) -> list[dict]:
    """
    Returns a list of render contexts for every tracked record that was
    broken or tied-as-best within the last `days` days.

    Each context dict is ready to pass directly to render_slides().
    """
    from pwhl_btn.db.db_config import get_engine
    from pwhl_btn.db.db_queries import _logo_uri, _pwhl_logo_uri, _player_photo_uri

    engine  = get_engine(pool_pre_ping=True)
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
                # For player records team_name holds the player's full name;
                # for team records it holds the team name / code.
                prev_player_name = getattr(pi, "team_name", None)
                is_player_record = (prev_player_name and prev_player_name != pi.team_code)
                prev_holders.append({
                    "team_code":    pi.team_code,
                    "display_name": prev_player_name if is_player_record else pi.team_code,
                    "logo":         _logo_uri(pi.team_code),
                    "player_photo": _player_photo_uri(prev_player_name) if is_player_record else None,
                    "game_date":    _fmt_date(pi.date),
                    "opponent":     f"vs {opp}",
                    "score":        f"{ts}-{os_}",
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

                # Featured player: prefer top scorer; fall back to inst.team_name
                # when the record is an individual one (team_name holds player name).
                inst_player_name = getattr(inst, "team_name", None)
                _is_player_rec   = (inst_player_name and inst_player_name != inst.team_code)
                if scorers:
                    featured_name = scorers[0]["name"]
                elif _is_player_rec:
                    featured_name = inst_player_name
                else:
                    featured_name = None
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
                    "badge_text":         rec.badge_text,
                    # Slide 2
                    "scorers":            scorers,
                    "include_detail_slide": rec.detail_slide,
                    # Meta
                    "season":    SEASON_ID,
                    "pwhl_logo": _pwhl_logo_uri(),
                })

    return results


# ── Top attendance leaderboard ────────────────────────────────────────────────

def get_top_attendance(top: int = 3) -> list[dict]:
    """
    Returns the top `top` highest-attended completed games of the current season.
    Each dict has: home_code, away_code, home_score, away_score, result_type,
    overtime_periods, venue, attendance, date.
    """
    from pwhl_btn.db.db_config import get_engine

    engine = get_engine(pool_pre_ping=True)

    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT
                g.date,
                ht.team_code  AS home_code,
                at.team_code  AS away_code,
                g.home_score,
                g.away_score,
                g.result_type,
                g.overtime_periods,
                g.venue,
                g.attendance
            FROM games g
            JOIN teams ht ON ht.team_id = g.home_team_id AND ht.season_id = g.season_id
            JOIN teams at ON at.team_id = g.away_team_id AND at.season_id = g.season_id
            WHERE g.season_id   = :sid
              AND g.game_status = 'Final'
              AND g.attendance IS NOT NULL
              AND g.attendance  > 0
            ORDER BY g.attendance DESC
            LIMIT :top
        """), {"sid": SEASON_ID, "top": top}).mappings().all()

    return [dict(r) for r in rows]


# ── Hat trick detector ─────────────────────────────────────────────────────────

def check_recent_hat_tricks(days: int = 1) -> list[dict]:
    """
    Returns one context dict per player who scored 3+ goals in a single game
    within the last `days` days.  These are notable events, not season records.
    """
    from pwhl_btn.db.db_config import get_engine
    from pwhl_btn.db.db_queries import _logo_uri, _pwhl_logo_uri, _player_photo_uri

    engine = get_engine(pool_pre_ping=True)
    cutoff = date.today() - timedelta(days=days)
    results = []

    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT
                s.game_id,
                s.player_id,
                CONCAT(p.first_name, ' ', p.last_name) AS player_name,
                s.team_id,
                t.team_code,
                t.team_name,
                g.date,
                ht.team_code  AS home_code,
                at.team_code  AS away_code,
                g.home_score,
                g.away_score,
                s.goals,
                s.assists,
                s.points
            FROM player_game_stats s
            JOIN players p  ON p.player_id = s.player_id
            JOIN teams   t  ON t.team_id   = s.team_id
            JOIN games   g  ON g.game_id   = s.game_id
            JOIN teams   ht ON ht.team_id  = g.home_team_id
            JOIN teams   at ON at.team_id  = g.away_team_id
            WHERE g.season_id = :sid
              AND g.game_status = 'Final'
              AND s.goals >= 3
              AND g.date >= :cutoff
            ORDER BY s.goals DESC, g.date DESC
        """), {"sid": SEASON_ID, "cutoff": cutoff}).fetchall()

        for r in rows:
            game_result, opp_code = _game_result_str(
                r.team_code, r.home_code, r.home_score, r.away_score
            )
            badge_label = "Hat Trick" if r.goals == 3 else f"{r.goals}-Goal Game"
            record_name = f"HAT TRICK" if r.goals == 3 else f"{r.goals}-GOAL GAME"

            results.append({
                "record_id":            f"hat_trick_{r.player_id}_{r.game_id}",
                "record_name":          record_name,
                "new_value":            r.goals,
                "new_value_unit":       "GOALS",
                "new_team_code":        r.team_code,
                "new_team_name":        r.player_name,
                "new_team_logo":        _logo_uri(r.team_code),
                "new_game_result":      game_result,
                "new_game_opponent":    opp_code,
                "new_game_date":        _fmt_date(r.date),
                "player_photo":         _player_photo_uri(r.player_name),
                "featured_player_name": r.player_name,
                "prev_value":           0,
                "prev_holders":         [],
                "prev_holders_label":   "—",
                "is_tie":               False,
                "badge_text":           badge_label,
                "hide_prev":            True,
                "scorers":              [{
                    "name":    r.player_name,
                    "goals":   r.goals,
                    "assists": r.assists,
                    "points":  r.points,
                }],
                "include_detail_slide": False,
                "season":               SEASON_ID,
                "pwhl_logo":            _pwhl_logo_uri(),
            })

    return results


# ── First career PWHL goal detector ───────────────────────────────────────────

def check_recent_first_goals(days: int = 1) -> list[dict]:
    """
    Returns one context dict per player who scored their first ever career
    PWHL goal in the last `days` days.
    """
    from pwhl_btn.db.db_config import get_engine
    from pwhl_btn.db.db_queries import _logo_uri, _pwhl_logo_uri, _player_photo_uri

    engine = get_engine(pool_pre_ping=True)
    cutoff = date.today() - timedelta(days=days)
    results = []

    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT
                s.game_id,
                s.player_id,
                CONCAT(p.first_name, ' ', p.last_name) AS player_name,
                s.team_id,
                t.team_code,
                t.team_name,
                g.date,
                ht.team_code  AS home_code,
                at.team_code  AS away_code,
                g.home_score,
                g.away_score,
                s.goals,
                s.assists,
                s.points
            FROM player_game_stats s
            JOIN players p  ON p.player_id = s.player_id
            JOIN teams   t  ON t.team_id   = s.team_id
            JOIN games   g  ON g.game_id   = s.game_id
            JOIN teams   ht ON ht.team_id  = g.home_team_id
            JOIN teams   at ON at.team_id  = g.away_team_id
            WHERE g.game_status = 'Final'
              AND g.date >= :cutoff
              AND s.goals > 0
              AND NOT EXISTS (
                  SELECT 1
                  FROM player_game_stats s2
                  JOIN games g2 ON g2.game_id = s2.game_id
                  WHERE s2.player_id = s.player_id
                    AND s2.goals > 0
                    AND g2.date < g.date
              )
            ORDER BY g.date DESC
        """), {"cutoff": cutoff}).fetchall()

        for r in rows:
            game_result, opp_code = _game_result_str(
                r.team_code, r.home_code, r.home_score, r.away_score
            )
            results.append({
                "record_id":            f"first_goal_{r.player_id}",
                "record_name":          "FIRST CAREER PWHL GOAL",
                "new_value":            1,
                "new_value_unit":       "GOAL",
                "new_team_code":        r.team_code,
                "new_team_name":        r.player_name,
                "new_team_logo":        _logo_uri(r.team_code),
                "new_game_result":      game_result,
                "new_game_opponent":    opp_code,
                "new_game_date":        _fmt_date(r.date),
                "player_photo":         _player_photo_uri(r.player_name),
                "featured_player_name": r.player_name,
                "prev_value":           0,
                "prev_holders":         [],
                "prev_holders_label":   "First in Career",
                "is_tie":               False,
                "badge_text":           "Milestone",
                "hide_prev":            True,
                "scorers":              [],
                "include_detail_slide": False,
                "season":               SEASON_ID,
                "pwhl_logo":            _pwhl_logo_uri(),
            })

    return results


# ── Shared streak helper ───────────────────────────────────────────────────────

def _compute_streaks(rows, has_streak_fn):
    """
    Given game rows for a single player ordered by date asc, compute all
    consecutive-game streaks where has_streak_fn(row) is True.

    Returns a list of streak row-lists, longest first.
    """
    streaks = []
    current = []
    for r in rows:
        if has_streak_fn(r):
            current.append(r)
        else:
            if current:
                streaks.append(current)
            current = []
    if current:
        streaks.append(current)
    streaks.sort(key=len, reverse=True)
    return streaks


def _streak_prev_holders(rows_by_player, season_best, has_streak_fn,
                         logo_fn, fmt_date_fn):
    """
    Build prev_holders for a streak record: any player (other than the new
    record holder, who is excluded from rows_by_player) whose longest streak
    equals season_best.  Uses player_name as the display 'team_code' field.
    """
    prev = []
    for player_rows in rows_by_player.values():
        for streak in _compute_streaks(player_rows, has_streak_fn):
            if len(streak) == season_best:
                last = streak[-1]
                opp = last.away_code if last.team_code == last.home_code else last.home_code
                ts  = last.home_score if last.team_code == last.home_code else last.away_score
                os_ = last.away_score if last.team_code == last.home_code else last.home_score
                prev.append({
                    "team_code": last.player_name,
                    "logo":      logo_fn(last.team_code),
                    "game_date": fmt_date_fn(last.date),
                    "opponent":  f"vs {opp}",
                    "score":     f"{ts}-{os_}",
                })
            break  # only the longest streak per player
    return prev


# ── Player point streak detector ──────────────────────────────────────────────

def check_recent_point_streaks(days: int = 1) -> list[dict]:
    """
    Returns a context dict for any player whose consecutive-games-with-a-point
    streak reached a new season best within the last `days` days.
    """
    from itertools import groupby
    from pwhl_btn.db.db_config import get_engine
    from pwhl_btn.db.db_queries import _logo_uri, _pwhl_logo_uri, _player_photo_uri

    engine = get_engine(pool_pre_ping=True)
    cutoff = date.today() - timedelta(days=days)
    results = []

    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT
                s.player_id,
                CONCAT(p.first_name, ' ', p.last_name) AS player_name,
                s.team_id,
                t.team_code,
                s.game_id,
                g.date,
                ht.team_code  AS home_code,
                at.team_code  AS away_code,
                g.home_score,
                g.away_score,
                s.points
            FROM player_game_stats s
            JOIN players p  ON p.player_id = s.player_id
            JOIN teams   t  ON t.team_id   = s.team_id
            JOIN games   g  ON g.game_id   = s.game_id
            JOIN teams   ht ON ht.team_id  = g.home_team_id
            JOIN teams   at ON at.team_id  = g.away_team_id
            WHERE g.season_id = :sid AND g.game_status = 'Final'
            ORDER BY s.player_id, g.date, s.game_id
        """), {"sid": SEASON_ID}).fetchall()

    has_point = lambda r: r.points > 0

    rows_by_player = {}
    for player_id, player_rows in groupby(rows, key=lambda r: r.player_id):
        rows_by_player[player_id] = list(player_rows)

    # Season-best streak length across all players
    season_best = 0
    for player_rows in rows_by_player.values():
        streaks = _compute_streaks(player_rows, has_point)
        if streaks and len(streaks[0]) > season_best:
            season_best = len(streaks[0])

    if season_best == 0:
        return results

    seen = set()
    for player_id, player_rows in rows_by_player.items():
        for streak in _compute_streaks(player_rows, has_point):
            if len(streak) < season_best:
                break
            last = streak[-1]
            if last.date < cutoff or player_id in seen:
                continue
            seen.add(player_id)

            game_result, opp_code = _game_result_str(
                last.team_code, last.home_code, last.home_score, last.away_score
            )
            other_rows   = {pid: r for pid, r in rows_by_player.items() if pid != player_id}
            prev_holders = _streak_prev_holders(other_rows, season_best, has_point, _logo_uri, _fmt_date)
            prev_value   = season_best if prev_holders else season_best - 1
            is_tie       = bool(prev_holders)

            results.append({
                "record_id":            f"point_streak_{player_id}",
                "record_name":          f"LONGEST POINT STREAK — {last.player_name}",
                "new_value":            season_best,
                "new_value_unit":       "GAMES",
                "new_team_code":        last.team_code,
                "new_team_name":        last.player_name,
                "new_team_logo":        _logo_uri(last.team_code),
                "new_game_result":      game_result,
                "new_game_opponent":    opp_code,
                "new_game_date":        _fmt_date(last.date),
                "player_photo":         _player_photo_uri(last.player_name),
                "featured_player_name": last.player_name,
                "prev_value":           prev_value,
                "prev_holders":         prev_holders,
                "prev_holders_label":   (prev_holders[0]["team_code"] if prev_holders else "None"),
                "is_tie":               is_tie,
                "badge_text":           "Point Streak" if is_tie else None,
                "hide_prev":            not prev_holders and prev_value == 0,
                "scorers":              [],
                "include_detail_slide": False,
                "season":               SEASON_ID,
                "pwhl_logo":            _pwhl_logo_uri(),
            })

    return results


# ── Goalie shutout streak detector ────────────────────────────────────────────

def check_recent_shutout_streaks(days: int = 1) -> list[dict]:
    """
    Returns a context dict for any goalie whose consecutive-games-without-
    conceding reached a new season best within `days` days.
    Only counts games where the goalie played at least 55 minutes (full game).
    """
    from itertools import groupby
    from pwhl_btn.db.db_config import get_engine
    from pwhl_btn.db.db_queries import _logo_uri, _pwhl_logo_uri, _player_photo_uri

    engine = get_engine(pool_pre_ping=True)
    cutoff = date.today() - timedelta(days=days)
    results = []

    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT
                s.player_id,
                CONCAT(p.first_name, ' ', p.last_name) AS player_name,
                s.team_id,
                t.team_code,
                s.game_id,
                g.date,
                ht.team_code  AS home_code,
                at.team_code  AS away_code,
                g.home_score,
                g.away_score,
                s.goals_against,
                s.minutes_played
            FROM goalie_game_stats s
            JOIN players p  ON p.player_id = s.player_id
            JOIN teams   t  ON t.team_id   = s.team_id
            JOIN games   g  ON g.game_id   = s.game_id
            JOIN teams   ht ON ht.team_id  = g.home_team_id
            JOIN teams   at ON at.team_id  = g.away_team_id
            WHERE g.season_id    = :sid
              AND g.game_status  = 'Final'
              AND s.minutes_played >= 55
            ORDER BY s.player_id, g.date, s.game_id
        """), {"sid": SEASON_ID}).fetchall()

    is_shutout = lambda r: r.goals_against == 0

    rows_by_player = {}
    for player_id, player_rows in groupby(rows, key=lambda r: r.player_id):
        rows_by_player[player_id] = list(player_rows)

    season_best = 0
    for player_rows in rows_by_player.values():
        streaks = _compute_streaks(player_rows, is_shutout)
        if streaks and len(streaks[0]) > season_best:
            season_best = len(streaks[0])

    if season_best == 0:
        return results

    seen = set()
    for player_id, player_rows in rows_by_player.items():
        for streak in _compute_streaks(player_rows, is_shutout):
            if len(streak) < season_best:
                break
            last = streak[-1]
            if last.date < cutoff or player_id in seen:
                continue
            seen.add(player_id)

            game_result, opp_code = _game_result_str(
                last.team_code, last.home_code, last.home_score, last.away_score
            )
            other_rows   = {pid: r for pid, r in rows_by_player.items() if pid != player_id}
            prev_holders = _streak_prev_holders(other_rows, season_best, is_shutout, _logo_uri, _fmt_date)
            prev_value   = season_best if prev_holders else season_best - 1
            is_tie       = bool(prev_holders)

            results.append({
                "record_id":            f"shutout_streak_{player_id}",
                "record_name":          f"LONGEST SHUTOUT STREAK — {last.player_name}",
                "new_value":            season_best,
                "new_value_unit":       "GAMES",
                "new_team_code":        last.team_code,
                "new_team_name":        last.player_name,
                "new_team_logo":        _logo_uri(last.team_code),
                "new_game_result":      game_result,
                "new_game_opponent":    opp_code,
                "new_game_date":        _fmt_date(last.date),
                "player_photo":         _player_photo_uri(last.player_name),
                "featured_player_name": last.player_name,
                "prev_value":           prev_value,
                "prev_holders":         prev_holders,
                "prev_holders_label":   (prev_holders[0]["team_code"] if prev_holders else "None"),
                "is_tie":               is_tie,
                "badge_text":           "Shutout Streak" if is_tie else None,
                "hide_prev":            not prev_holders and prev_value == 0,
                "scorers":              [],
                "include_detail_slide": False,
                "season":               SEASON_ID,
                "pwhl_logo":            _pwhl_logo_uri(),
            })

    return results
