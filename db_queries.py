"""
db_queries.py — Query functions that feed the BTN PWHL templates.

All public functions return plain dicts/lists — no SQLAlchemy objects
leave this module, so the renderers stay decoupled from the ORM.
"""

import os
from datetime import date, timedelta
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from db_config import get_db_url
DATABASE_URL = get_db_url()

engine  = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

# ── Team logo helper ───────────────────────────────────────────────────────────
TEAM_CODE_MAP = {
    "BOS": "BOS_50x50",
    "MIN": "MIN_50x50",
    "MTL": "MTL_50x50",
    "NY": "NY_50x50",
    "OTT": "OTT_50x50",
    "SEA": "SEA_50x50",
    "TOR": "TOR_50x50",
    "VAN": "VAN_50x50",
}

PLAYERS_DIR = Path(__file__).parent / "assets" / "players"

def _player_photo_uri(player_name: str):
    # firstname_lastname.jpg — e.g. rebecca_leslie.jpg
    slug = player_name.lower().replace(" ", "_").replace("-", "_").replace("'", "")
    for ext in ("jpg", "jpeg", "png", "webp"):
        p = PLAYERS_DIR / f"{slug}.{ext}"
        if p.exists():
            return p.resolve().as_uri()
    return None

def _logo_uri(team_code: str) -> str | None:
    name = TEAM_CODE_MAP.get(team_code.upper())
    if not name:
        return None
    p = Path(__file__).parent / "assets" / "logos" / f"{name}.png"
    return p.as_uri() if p.exists() else None


# ── Week range helpers ─────────────────────────────────────────────────────────
def _d(dt, fmt: str) -> str:
    """Cross-platform date format — strips leading zeros on both Windows and Linux."""
    return dt.strftime(fmt).replace(" 0", " ").lstrip("0") or "0"


def _last_week_bounds():
    """Returns (monday, sunday) of the most recently completed week."""
    today  = date.today()
    sunday = today - timedelta(days=today.isoweekday() % 7)
    monday = sunday - timedelta(days=6)
    return monday, sunday


def _format_range(start, end) -> str:
    if start.month == end.month:
        return f"{_d(start, '%b %d')} \u2013 {_d(end, '%d, %Y')}".upper()
    return f"{_d(start, '%b %d')} \u2013 {_d(end, '%b %d, %Y')}".upper()


# ── Core query: games in a date range ─────────────────────────────────────────
def get_weekly_games(start: date = None, end: date = None) -> list[dict]:
    """
    Returns all final games in [start, end] inclusive, ordered by date.
    Defaults to last completed week.
    """
    if not start or not end:
        start, end = _last_week_bounds()

    session = Session()
    try:
        rows = session.execute(text("""
            SELECT
                g.game_id,
                g.date,
                g.home_score,
                g.away_score,
                g.result_type,
                ht.team_code AS home_code,
                ht.team_name AS home_name,
                at.team_code AS away_code,
                at.team_name AS away_name
            FROM games g
            JOIN teams ht ON ht.team_id = g.home_team_id
            JOIN teams at ON at.team_id = g.away_team_id
            WHERE g.date BETWEEN :start AND :end
              AND g.game_status = 'final'
            ORDER BY g.date ASC
        """), {"start": start, "end": end}).fetchall()

        games = []
        for r in rows:
            games.append({
                "game_id":     r.game_id,
                "date_short":  _d(r.date, "%a %m/%d").upper(),
                "home_abbr":   r.home_code,
                "away_abbr":   r.away_code,
                "home_team":   r.home_name,
                "away_team":   r.away_name,
                "home_score":  r.home_score,
                "away_score":  r.away_score,
                "result_type": r.result_type or "REG",
                "home_logo":   _logo_uri(r.home_code),
                "away_logo":   _logo_uri(r.away_code),
            })
        return games
    finally:
        session.close()


# ── Standings ──────────────────────────────────────────────────────────────────
def get_standings(season_id: int = 8) -> list[dict]:
    """
    Computes current standings from the games table.
    Points: W=2, OTW=2, OTL=1, SOL=1, L=0
    Returns list sorted by points desc, then wins desc.
    """
    session = Session()
    try:
        rows = session.execute(text("""
            WITH results AS (
                -- Home team perspective
                SELECT
                    g.home_team_id                          AS team_id,
                    g.result_type,
                    CASE WHEN g.home_score > g.away_score THEN 1 ELSE 0 END AS win,
                    CASE WHEN g.home_score < g.away_score
                          AND g.result_type = 'REG'         THEN 1 ELSE 0 END AS loss,
                    CASE WHEN g.home_score > g.away_score
                          AND g.result_type IN ('OT','SO')  THEN 1 ELSE 0 END AS otw,
                    CASE WHEN g.home_score < g.away_score
                          AND g.result_type = 'OT'          THEN 1 ELSE 0 END AS otl,
                    CASE WHEN g.home_score < g.away_score
                          AND g.result_type = 'SO'          THEN 1 ELSE 0 END AS sol,
                    'home'                                  AS venue
                FROM games g WHERE g.season_id = :sid AND g.game_status = 'final'

                UNION ALL

                -- Away team perspective
                SELECT
                    g.away_team_id,
                    g.result_type,
                    CASE WHEN g.away_score > g.home_score THEN 1 ELSE 0 END,
                    CASE WHEN g.away_score < g.home_score
                          AND g.result_type = 'REG'         THEN 1 ELSE 0 END,
                    CASE WHEN g.away_score > g.home_score
                          AND g.result_type IN ('OT','SO')  THEN 1 ELSE 0 END,
                    CASE WHEN g.away_score < g.home_score
                          AND g.result_type = 'OT'          THEN 1 ELSE 0 END,
                    CASE WHEN g.away_score < g.home_score
                          AND g.result_type = 'SO'          THEN 1 ELSE 0 END,
                    'away'
                FROM games g WHERE g.season_id = :sid AND g.game_status = 'final'
            )
            SELECT
                t.team_id,
                t.team_name,
                t.team_code,
                COUNT(*)                        AS gp,
                SUM(win)                        AS wins,
                SUM(loss)                       AS losses,
                SUM(otw)                        AS otw,
                SUM(otl)                        AS otl,
                SUM(sol)                        AS sol,
                SUM(win)*2 + SUM(otl) + SUM(sol) AS points,
                -- Home record
                SUM(CASE WHEN venue='home' AND win=1  THEN 1 ELSE 0 END) AS hw,
                SUM(CASE WHEN venue='home' AND loss=1 THEN 1 ELSE 0 END) AS hl,
                SUM(CASE WHEN venue='home' AND (otl=1 OR sol=1) THEN 1 ELSE 0 END) AS hotl,
                -- Away record
                SUM(CASE WHEN venue='away' AND win=1  THEN 1 ELSE 0 END) AS aw,
                SUM(CASE WHEN venue='away' AND loss=1 THEN 1 ELSE 0 END) AS al,
                SUM(CASE WHEN venue='away' AND (otl=1 OR sol=1) THEN 1 ELSE 0 END) AS aotl
            FROM results r
            JOIN teams t ON t.team_id = r.team_id
            GROUP BY t.team_id, t.team_name, t.team_code
            ORDER BY points DESC, wins DESC
        """), {"sid": season_id}).fetchall()

        return [{
            "abbr":        r.team_code,
            "name":        r.team_name,
            "logo":        _logo_uri(r.team_code),
            "gp":          r.gp,
            "wins":        r.wins,
            "losses":      r.losses,
            "otw":         r.otw,
            "otl":         r.otl + r.sol,   # combined OTL+SOL for display
            "home_record": f"{r.hw}-{r.hl}-{r.hotl}",
            "away_record": f"{r.aw}-{r.al}-{r.aotl}",
            "points":      r.points,
        } for r in rows]
    finally:
        session.close()


# ── Teaser stats ───────────────────────────────────────────────────────────────
def get_weekly_teaser(start: date = None, end: date = None,
                      season_id: int = 8) -> dict:
    """
    Returns hook-slide teaser: games played, total goals, points leader.
    """
    if not start or not end:
        start, end = _last_week_bounds()

    session = Session()
    try:
        # Total goals this week
        goals_row = session.execute(text("""
            SELECT COALESCE(SUM(home_score + away_score), 0) AS total_goals,
                   COUNT(*) AS games_played
            FROM games
            WHERE date BETWEEN :start AND :end
              AND game_status = 'final'
        """), {"start": start, "end": end}).fetchone()

        # Season points leader
        leader_row = session.execute(text("""
            SELECT CONCAT(p.first_name, ' ', p.last_name) AS player_name,
                   SUM(s.points) AS total_points
            FROM player_game_stats s
            JOIN players p ON p.player_id = s.player_id
            JOIN games g   ON g.game_id   = s.game_id
            WHERE g.season_id = :sid
            GROUP BY p.player_id, player_name
            ORDER BY total_points DESC
            LIMIT 1
        """), {"sid": season_id}).fetchone()

        total_goals  = int(goals_row.total_goals)
        games_played = int(goals_row.games_played)
        leader_name  = leader_row.player_name if leader_row else "—"
        leader_pts   = int(leader_row.total_points) if leader_row else 0

        return {
            "games_played": games_played,
            "stat_line":    f"<em>{total_goals}</em> goals scored",
            "leader_name":  leader_name,
            "leader_stat":  f"{leader_pts} PTS",
        }
    finally:
        session.close()


# ── Story of the week: top player performance ─────────────────────────────────
def get_story_of_week(start: date = None, end: date = None) -> dict | None:
    """
    Auto-picks the most notable player performance from the week.
    Priority: hat tricks > 4-point games > 3-point games > season milestones.
    Returns a dict shaped for recap_slide3.html, or None if no data.
    """
    if not start or not end:
        start, end = _last_week_bounds()

    session = Session()
    try:
        rows = session.execute(text("""
            SELECT
                p.player_id,
                CONCAT(p.first_name, ' ', p.last_name) AS player_name,
                t.team_name,
                t.team_code,
                p.position,
                SUM(s.goals)   AS goals,
                SUM(s.assists) AS assists,
                SUM(s.points)  AS points,
                SUM(s.shots)   AS shots,
                COUNT(*)       AS games_played
            FROM player_game_stats s
            JOIN players p ON p.player_id = s.player_id
            JOIN teams   t ON t.team_id   = s.team_id
            JOIN games   g ON g.game_id   = s.game_id
            WHERE g.date BETWEEN :start AND :end
              AND g.game_status = 'final'
            GROUP BY p.player_id, player_name, t.team_name, t.team_code, p.position
            ORDER BY points DESC, goals DESC
            LIMIT 10
        """), {"start": start, "end": end}).fetchall()

        if not rows:
            return None

        # Pick best row using priority logic
        best = None
        for r in rows:
            if r.goals >= 3:          # hat trick or better
                best = r; break
        if not best:
            for r in rows:
                if r.points >= 4:     # 4-point game
                    best = r; break
        if not best:
            best = rows[0]            # highest points week overall

        goals   = int(best.goals)
        assists = int(best.assists)
        points  = int(best.points)

        # Pick badge
        if goals >= 3:
            event_type  = "HAT_TRICK"
            type_label  = "Hat Trick"
            icon        = "🎩"
            headline    = f"<em>{best.player_name.split()[-1]}</em> Records a Hat Trick"
        elif points >= 4:
            event_type  = "MULTI_POINT"
            type_label  = f"{points}-Point Week"
            icon        = "⚡"
            headline    = f"<em>{best.player_name.split()[-1]}</em> Dominates With a {points}-Point Performance"
        else:
            event_type  = "TOP_PERFORMER"
            type_label  = "Top Performer"
            icon        = "🏒"
            headline    = f"<em>{best.player_name.split()[-1]}</em> Leads the Week With {points} Points"

        return {
            "type":            event_type,
            "type_label":      type_label,
            "icon":            icon,
            "player_name":     best.player_name,
            "player_team":     best.team_name,
            "player_position": best.position or "F",
            "player_photo":    _player_photo_uri(best.player_name),
            "team_logo":       _logo_uri(best.team_code),
            "is_override":     False,
            "stats": [
                {"label": "Goals",   "value": str(goals)},
                {"label": "Assists", "value": str(assists)},
                {"label": "Points",  "value": str(points)},
            ],
            "headline": headline,
            "body": (
                f"{best.player_name} put together an outstanding week, recording "
                f"{goals} goal{'s' if goals != 1 else ''} and "
                f"{assists} assist{'s' if assists != 1 else ''} "
                f"across {int(best.games_played)} game{'s' if best.games_played != 1 else ''} "
                f"for {best.team_name}."
            ),
        }
    finally:
        session.close()


# ── Upcoming games (for weekly preview) ───────────────────────────────────────
def get_upcoming_games(days_ahead: int = 7) -> list[dict]:
    """
    Returns scheduled (non-final) games in the next N days.
    """
    start = date.today()
    end   = start + timedelta(days=days_ahead)

    session = Session()
    try:
        rows = session.execute(text("""
            SELECT
                g.game_id,
                g.date,
                ht.team_code AS home_code,
                ht.team_name AS home_name,
                at.team_code AS away_code,
                at.team_name AS away_name
            FROM games g
            JOIN teams ht ON ht.team_id = g.home_team_id
            JOIN teams at ON at.team_id = g.away_team_id
            WHERE g.date BETWEEN :start AND :end
              AND g.game_status != 'final'
            ORDER BY g.date ASC
        """), {"start": start, "end": end}).fetchall()

        return [{
            "game_id":   r.game_id,
            "date_short": _d(r.date, "%a %m/%d").upper(),
            "home_abbr":  r.home_code,
            "away_abbr":  r.away_code,
            "home_team":  r.home_name,
            "away_team":  r.away_name,
            "home_logo":  _logo_uri(r.home_code),
            "away_logo":  _logo_uri(r.away_code),
        } for r in rows]
    finally:
        session.close()



# ── Slide 1 player photo: random scorer or shutout goalie ─────────────────────
def get_slide1_player(start=None, end=None):
    """
    Picks a random player from:
      - Skaters who scored at least 1 goal this week, OR
      - Goalies with a shutout this week
    Returns dict with player_name, player_team, photo_uri (may be None).
    Returns None if no candidates found.
    """
    if not start or not end:
        start, end = _last_week_bounds()

    session = Session()
    try:
        # Skaters with at least 1 goal this week
        scorers = session.execute(text("""
            SELECT CONCAT(p.first_name, ' ', p.last_name) AS player_name,
                   t.team_name,
                   SUM(s.goals) AS goals
            FROM player_game_stats s
            JOIN players p ON p.player_id = s.player_id
            JOIN teams   t ON t.team_id   = s.team_id
            JOIN games   g ON g.game_id   = s.game_id
            WHERE g.date BETWEEN :start AND :end
              AND g.game_status = 'final'
            GROUP BY p.player_id, player_name, t.team_name
            HAVING goals > 0
        """), {"start": start, "end": end}).fetchall()

        # Goalies with a shutout (0 goals against, played full game)
        shutouts = session.execute(text("""
            SELECT CONCAT(p.first_name, ' ', p.last_name) AS player_name,
                   t.team_name
            FROM goalie_game_stats s
            JOIN players p ON p.player_id = s.player_id
            JOIN teams   t ON t.team_id   = s.team_id
            JOIN games   g ON g.game_id   = s.game_id
            WHERE g.date BETWEEN :start AND :end
              AND g.game_status = 'final'
              AND s.goals_against = 0
              AND s.minutes_played >= 55
              AND s.decision = 'W'
        """), {"start": start, "end": end}).fetchall()

        candidates = [{"player_name": r.player_name, "player_team": r.team_name}
                      for r in scorers]
        candidates += [{"player_name": r.player_name, "player_team": r.team_name}
                       for r in shutouts]

        if not candidates:
            return None

        import random
        pick = random.choice(candidates)
        pick["skater_photo"] = _player_photo_uri(pick["player_name"])
        return pick

    finally:
        session.close()


# ── Master function: everything the templates need ────────────────────────────
def get_template_data(start: date = None, end: date = None,
                      season_id: int = 8) -> dict:
    """
    Single entry point for both renderers.
    Returns the full data dict expected by all 4 recap slides + the preview.
    """
    if not start or not end:
        start, end = _last_week_bounds()

    games     = get_weekly_games(start, end)
    standings = get_standings(season_id)
    teaser    = get_weekly_teaser(start, end, season_id)
    event     = get_story_of_week(start, end)
    slide1    = get_slide1_player(start, end)
    upcoming  = get_upcoming_games()

    return {
        "season":     f"20{str(season_id + 17)[-2:]}–{str(season_id + 18)[-2:]}",  # e.g. 2025-26
        "week_range": _format_range(start, end),
        "week_end":   _d(end, "%b %d, %Y").upper(),
        "theme":      "light",
        "games":      games,
        "standings":  standings,
        "teaser":     teaser,
        "event":      event,
        "upcoming":      upcoming,
        "skater_photo":  slide1["skater_photo"] if slide1 else None,
        "skater_name":   slide1["player_name"]  if slide1 else None,
        "skater_team":   slide1["player_team"]  if slide1 else None,
    }


# ── Quick test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json

    print("Testing db_queries.py...\n")
    data = get_template_data()

    print(f"Week:      {data['week_range']}")
    print(f"Games:     {len(data['games'])}")
    print(f"Standings: {len(data['standings'])} teams")
    print(f"Teaser:    {data['teaser']}")
    print(f"Story:     {data['event']['player_name'] if data['event'] else 'None'}")
    print(f"Upcoming:  {len(data['upcoming'])} games")
    print("\n✅ All queries OK")
