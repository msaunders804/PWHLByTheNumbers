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

engine    = create_engine(DATABASE_URL)
Session   = sessionmaker(bind=engine)
SEASON_ID = 8

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


def _pwhl_logo_uri() -> str | None:
    p = Path(__file__).parent / "assets" / "logos" / "PWHL_logo.svg"
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


# ── Player Spotlight ───────────────────────────────────────────────────────────

def get_spotlight_player():
    """
    Picks a random skater who hasn't been featured yet.
    Excludes top 10 in points to surface lesser-known players.
    Returns dict with player info + season stats + league ranks.
    Returns None if all players have been featured (resets table).
    """
    session = Session()
    try:
        # Get already-featured player IDs
        featured = session.execute(text("""
            SELECT player_id FROM featured_players
        """)).fetchall()
        featured_ids = [r.player_id for r in featured]

        # Get top 10 in points to exclude
        top10 = session.execute(text("""
            SELECT s.player_id
            FROM player_game_stats s
            JOIN games g ON g.game_id = s.game_id
            WHERE g.season_id = :sid AND g.game_status = 'final'
            GROUP BY s.player_id
            ORDER BY SUM(s.goals + s.assists) DESC
            LIMIT 10
        """), {"sid": SEASON_ID}).fetchall()
        top10_ids = [r.player_id for r in top10]

        exclude_ids = list(set(featured_ids + top10_ids))
        exclude_clause = f"AND p.player_id NOT IN ({','.join(str(i) for i in exclude_ids)})" if exclude_ids else ""

        # Pick random skater with at least 1 game played
        candidates = session.execute(text(f"""
            SELECT p.player_id,
                   CONCAT(p.first_name, ' ', p.last_name) AS player_name,
                   t.team_name,
                   t.team_code,
                   p.position,
                   p.jersey_number,
                   p.nationality
            FROM players p
            JOIN (
                SELECT s2.player_id, s2.team_id
                FROM player_game_stats s2
                JOIN games g2 ON g2.game_id = s2.game_id
                WHERE g2.season_id = :sid
                GROUP BY s2.player_id, s2.team_id
            ) latest ON latest.player_id = p.player_id
            JOIN teams t ON t.team_id = latest.team_id AND t.season_id = :sid
            WHERE (p.position IS NULL OR p.position != 'G')
              {exclude_clause}
            ORDER BY RAND()
            LIMIT 1
        """), {"sid": SEASON_ID}).fetchone()

        # If everyone has been featured, reset and start again
        if not candidates:
            session.execute(text("DELETE FROM featured_players"))
            session.commit()
            return get_spotlight_player()

        pid = candidates.player_id

        # Season stats
        stats = session.execute(text("""
            SELECT SUM(s.goals)   AS goals,
                   SUM(s.assists) AS assists,
                   SUM(s.shots)   AS shots,
                   COUNT(s.game_id) AS gp
            FROM player_game_stats s
            JOIN games g ON g.game_id = s.game_id
            WHERE s.player_id = :pid
              AND g.season_id = :sid
              AND g.game_status = 'final'
        """), {"pid": pid, "sid": SEASON_ID}).fetchone()

        # League ranks
        def _rank(metric, col):
            # col uses s2 alias to match the subquery table alias
            col_fixed = col.replace("s.", "s2.")
            row = session.execute(text(f"""
                SELECT COUNT(*) + 1 AS rnk
                FROM (
                    SELECT s2.player_id, SUM({col_fixed}) AS val
                    FROM player_game_stats s2
                    JOIN games g2 ON g2.game_id = s2.game_id
                    WHERE g2.season_id = :sid AND g2.game_status = 'final'
                    GROUP BY s2.player_id
                ) ranked
                WHERE val > :metric
            """), {"sid": SEASON_ID, "metric": metric or 0}).fetchone()
            return f"#{row.rnk} in league"

        goals   = int(stats.goals or 0)
        assists = int(stats.assists or 0)
        points  = goals + assists
        shots   = int(stats.shots or 0)
        gp      = int(stats.gp or 1)

        # avg TOI from players table (pre-computed by load_game/add_toi.py)
        toi_row = session.execute(text("""
            SELECT avg_toi_seconds FROM players WHERE player_id = :pid
        """), {"pid": pid}).fetchone()
        avg_toi_sec = int(toi_row.avg_toi_seconds) if toi_row and toi_row.avg_toi_seconds else None
        toi_str = f"{avg_toi_sec // 60}:{avg_toi_sec % 60:02d}" if avg_toi_sec else "—"

        # TOI rank (only if we have data)
        if avg_toi_sec:
            toi_rank_row = session.execute(text("""
                SELECT COUNT(*) + 1 AS rnk
                FROM players
                WHERE avg_toi_seconds > :val AND avg_toi_seconds IS NOT NULL
            """), {"val": avg_toi_sec}).fetchone()
            toi_rank_str = f"#{toi_rank_row.rnk} in league"
        else:
            toi_rank_str = "—"

        # Record as featured
        session.execute(text("""
            INSERT IGNORE INTO featured_players (player_id, featured_date)
            VALUES (:pid, CURDATE())
        """), {"pid": pid})
        session.commit()

        return {
            "player_id":     pid,
            "player_name":   candidates.player_name,
            "player_team":   candidates.team_name,
            "position":      candidates.position or "F",
            "jersey_number": candidates.jersey_number or "—",
            "nationality":   candidates.nationality or "—",
            "goals":         goals,
            "assists":       assists,
            "points":        points,
            "shots":         shots,
            "goals_rank":    _rank(goals,   "s.goals"),
            "assists_rank":  _rank(assists, "s.assists"),
            "points_rank":   _rank(points,  "s.goals + s.assists"),
            "shots_rank":    _rank(shots,   "s.shots"),
            "toi":           toi_str,
            "toi_rank":      toi_rank_str,
            "player_photo":  _official_photo_uri(pid),
            "pwhl_logo":     _pwhl_logo_uri(),
            "season_label":  f"Season {SEASON_ID} • {goals + assists} PTS",
        }

    finally:
        session.close()


def _official_photo_uri(player_id: int) -> str | None:
    """
    Returns player photo URL. Uses leaguestat CDN (always available),
    falling back to local assets if present.
    """
    # Local file takes priority if it exists
    base = Path(__file__).parent.parent / "assets" / "players" / "official"
    for ext in ["jpg", "jpeg", "png", "webp"]:
        p = base / f"{player_id}.{ext}"
        if p.exists():
            return p.resolve().as_uri()
    # CDN fallback — leaguestat hosts player images at a predictable URL
    return f"https://assets.leaguestat.com/pwhl/240x240/{player_id}.jpg"


def get_spotlight_goalie(player_id: int, session) -> dict:
    """Returns goalie season stats + league ranks for spotlight."""

    stats = session.execute(text("""
        SELECT COUNT(DISTINCT g.game_id)                          AS gp,
               SUM(s.goals_against)                               AS ga,
               SUM(s.minutes_played) / 60.0                       AS toi_min,
               SUM(s.saves)                                        AS saves,
               SUM(s.shots_against)                               AS shots_against,
               SUM(CASE WHEN s.decision = 'W' THEN 1 ELSE 0 END)  AS wins,
               SUM(CASE WHEN s.goals_against = 0
                         AND s.decision = 'W' THEN 1 ELSE 0 END)  AS shutouts
        FROM goalie_game_stats s
        JOIN games g ON g.game_id = s.game_id
        WHERE s.player_id = :pid
          AND g.season_id = :sid
          AND g.game_status = 'final'
    """), {"pid": player_id, "sid": SEASON_ID}).fetchone()

    toi_min      = float(stats.toi_min or 0)
    gaa          = round((stats.ga or 0) / (toi_min / 60), 2) if toi_min > 0 else 0.0
    sv_pct_val   = round((stats.saves or 0) / (stats.shots_against or 1), 3)
    wins         = int(stats.wins or 0)
    shutouts     = int(stats.shutouts or 0)
    gp           = int(stats.gp or 0)

    def _goalie_rank(metric, expr, lower_is_better=False):
        op = "<" if lower_is_better else ">"
        row = session.execute(text(f"""
            SELECT COUNT(*) + 1 AS rnk FROM (
                SELECT s2.player_id, {expr} AS val
                FROM goalie_game_stats s2
                JOIN games g2 ON g2.game_id = s2.game_id
                WHERE g2.season_id = :sid AND g2.game_status = 'final'
                GROUP BY s2.player_id
                HAVING SUM(s2.minutes_played) / 60.0 >= 60
            ) ranked WHERE val {op} :metric
        """), {"sid": SEASON_ID, "metric": metric}).fetchone()
        return f"#{row.rnk}"

    return {
        "gp":              gp,
        "gaa":             f"{gaa:.2f}",
        "sv_pct":          f"{sv_pct_val:.3f}",
        "wins":            wins,
        "shutouts":        shutouts,
        "gaa_rank_num":    _goalie_rank(gaa,       "SUM(s2.goals_against) / (SUM(s2.minutes_played) / 3600.0)", lower_is_better=True),
        "sv_rank_num":     _goalie_rank(sv_pct_val,"SUM(s2.saves) / SUM(s2.shots_against)"),
        "wins_rank_num":   _goalie_rank(wins,      "SUM(CASE WHEN s2.decision='W' THEN 1 ELSE 0 END)"),
        "shutouts_rank_num": _goalie_rank(shutouts,"SUM(CASE WHEN s2.goals_against=0 AND s2.decision='W' THEN 1 ELSE 0 END)"),
    }


# ── Weekly Preview ─────────────────────────────────────────────────────────────

def get_upcoming_schedule(start_date, end_date):
    """
    Returns games scheduled between start_date and end_date (not yet final).
    Groups by day for the schedule slide.
    """
    session = Session()
    try:
        rows = session.execute(text("""
            SELECT g.game_id,
                   g.date,
                   g.home_team_id, ht.team_code AS home_code, ht.team_name AS home_name,
                   g.away_team_id, at.team_code AS away_code, at.team_name AS away_name,
                   g.game_time, g.broadcast
            FROM games g
            JOIN teams ht ON ht.team_id = g.home_team_id AND ht.season_id = :sid
            JOIN teams at ON at.team_id = g.away_team_id AND at.season_id = :sid
            WHERE g.season_id  = :sid
              AND g.date       BETWEEN :start AND :end
              AND g.game_status != 'final'
            ORDER BY g.date, g.game_time
        """), {"sid": SEASON_ID, "start": start_date, "end": end_date}).fetchall()

        # Group by day
        from collections import OrderedDict
        from datetime import datetime as _dt
        days = OrderedDict()
        for r in rows:
            d = str(r.date)
            if d not in days:
                dt = _dt.strptime(d, "%Y-%m-%d")
                days[d] = {
                    "day_name": dt.strftime("%A").upper(),
                    "date_str": dt.strftime("%b %d").upper(),
                    "games": []
                }
            days[d]["games"].append({
                "game_id":   r.game_id,
                "away_team": r.away_code,
                "home_team": r.home_code,
                "away_logo": _logo_uri(r.away_code),
                "home_logo": _logo_uri(r.home_code),
                "time":      r.game_time or "TBD",
                "broadcast": r.broadcast or "",
            })
        return list(days.values())
    finally:
        session.close()


def get_game_to_watch(start_date, end_date):
    """
    Scores each game this week and returns the best matchup.
    Scoring: standings closeness + combined points + head-to-head interest.
    Returns game dict + top players from each team.
    """
    session = Session()
    try:
        # Current standings (points)
        standings = session.execute(text("""
            SELECT t.team_id, t.team_code, t.team_name,
                   SUM(CASE
                       WHEN (g.home_team_id = t.team_id AND g.home_score > g.away_score) OR
                            (g.away_team_id = t.team_id AND g.away_score > g.home_score)
                       THEN 2
                       WHEN g.result_type IN ('OT','SO')
                        AND ((g.home_team_id = t.team_id AND g.home_score < g.away_score) OR
                             (g.away_team_id = t.team_id AND g.away_score < g.home_score))
                       THEN 1
                       ELSE 0 END) AS pts,
                   COUNT(g.game_id) AS gp,
                   SUM(CASE
                       WHEN (g.home_team_id = t.team_id AND g.home_score > g.away_score) OR
                            (g.away_team_id = t.team_id AND g.away_score > g.home_score)
                       THEN 1 ELSE 0 END) AS wins,
                   SUM(CASE
                       WHEN (g.home_team_id = t.team_id AND g.home_score < g.away_score AND g.result_type = 'REG') OR
                            (g.away_team_id = t.team_id AND g.away_score < g.home_score AND g.result_type = 'REG')
                       THEN 1 ELSE 0 END) AS losses,
                   SUM(CASE
                       WHEN g.result_type IN ('OT','SO')
                        AND ((g.home_team_id = t.team_id AND g.home_score < g.away_score) OR
                             (g.away_team_id = t.team_id AND g.away_score < g.home_score))
                       THEN 1 ELSE 0 END) AS ot_losses
            FROM teams t
            LEFT JOIN games g ON (g.home_team_id = t.team_id OR g.away_team_id = t.team_id)
                              AND g.season_id = :sid AND g.game_status = 'final'
            WHERE t.season_id = :sid
            GROUP BY t.team_id, t.team_code, t.team_name
            ORDER BY pts DESC
        """), {"sid": SEASON_ID}).fetchall()

        pts_map  = {r.team_id: int(r.pts or 0)      for r in standings}
        rank_map = {r.team_id: i+1 for i, r in enumerate(standings)}
        rec_map  = {r.team_id: f"{int(r.wins or 0)}-{int(r.losses or 0)}-{int(r.ot_losses or 0)}"
                    for r in standings}
        name_map = {r.team_id: r.team_name for r in standings}
        code_map = {r.team_id: r.team_code for r in standings}

        # Upcoming games this week
        games = session.execute(text("""
            SELECT g.game_id, g.date, g.game_time, g.broadcast,
                   g.home_team_id, g.away_team_id
            FROM games g
            WHERE g.season_id = :sid
              AND g.date BETWEEN :start AND :end
              AND g.game_status != 'final'
            ORDER BY g.date
        """), {"sid": SEASON_ID, "start": start_date, "end": end_date}).fetchall()

        if not games:
            return None

        # Score each game
        best_game = None
        best_score = -1
        for g in games:
            h, a = g.home_team_id, g.away_team_id
            rank_diff    = abs(rank_map.get(h, 8) - rank_map.get(a, 8))
            combined_pts = pts_map.get(h, 0) + pts_map.get(a, 0)
            # Closer in standings = more interesting; higher combined pts = better teams
            score = combined_pts - (rank_diff * 5)
            if score > best_score:
                best_score = score
                best_game  = g

        if not best_game:
            return None

        h_id, a_id = best_game.home_team_id, best_game.away_team_id

        # Top 2 players from each team by points this season
        def _top_players(team_id, n=2):
            rows = session.execute(text("""
                SELECT CONCAT(p.first_name, ' ', p.last_name) AS name,
                       SUM(s.goals)   AS goals,
                       SUM(s.assists) AS assists,
                       SUM(s.goals + s.assists) AS points
                FROM player_game_stats s
                JOIN players p ON p.player_id = s.player_id
                JOIN games g ON g.game_id = s.game_id
                WHERE s.team_id = :tid AND g.season_id = :sid AND g.game_status = 'final'
                GROUP BY p.player_id, p.first_name, p.last_name
                ORDER BY points DESC
                LIMIT :n
            """), {"tid": team_id, "sid": SEASON_ID, "n": n}).fetchall()
            return [{"name": r.name, "team": code_map.get(team_id, ""),
                     "goals": int(r.goals or 0), "assists": int(r.assists or 0),
                     "points": int(r.points or 0)} for r in rows]

        from datetime import datetime as _dt
        date_str = _dt.strptime(str(best_game.date), "%Y-%m-%d").strftime("%a %b %d").upper()

        return {
            "game_id":        best_game.game_id,
            "gtw_home_team":  code_map.get(h_id, ""),
            "gtw_away_team":  code_map.get(a_id, ""),
            "gtw_home_logo":  _logo_uri(code_map.get(h_id, "")),
            "gtw_away_logo":  _logo_uri(code_map.get(a_id, "")),
            "gtw_home_record": rec_map.get(h_id, ""),
            "gtw_away_record": rec_map.get(a_id, ""),
            "gtw_date":       date_str,
            "gtw_time":       best_game.game_time or "TBD",
            "key_players":    _top_players(a_id) + _top_players(h_id),
            "why_watch":      None,  # filled by AI in renderer
        }
    finally:
        session.close()


def get_preview_standings():
    """Current standings formatted for the preview standings slide."""
    session = Session()
    try:
        rows = session.execute(text("""
            SELECT t.team_id, t.team_code, t.team_name,
                   SUM(CASE
                       WHEN (g.home_team_id = t.team_id AND g.home_score > g.away_score) OR
                            (g.away_team_id = t.team_id AND g.away_score > g.home_score)
                       THEN 2
                       WHEN g.result_type IN ('OT','SO')
                        AND ((g.home_team_id = t.team_id AND g.home_score < g.away_score) OR
                             (g.away_team_id = t.team_id AND g.away_score < g.home_score))
                       THEN 1
                       ELSE 0 END) AS pts,
                   COUNT(g.game_id) AS gp,
                   SUM(CASE WHEN (g.home_team_id=t.team_id AND g.home_score>g.away_score) OR
                                 (g.away_team_id=t.team_id AND g.away_score>g.home_score)
                            THEN 1 ELSE 0 END) AS wins,
                   SUM(CASE WHEN (g.home_team_id=t.team_id AND g.home_score<g.away_score AND g.result_type='REG') OR
                                 (g.away_team_id=t.team_id AND g.away_score<g.home_score AND g.result_type='REG')
                            THEN 1 ELSE 0 END) AS losses,
                   SUM(CASE WHEN g.result_type IN ('OT','SO')
                             AND ((g.home_team_id=t.team_id AND g.home_score<g.away_score) OR
                                  (g.away_team_id=t.team_id AND g.away_score<g.home_score))
                            THEN 1 ELSE 0 END) AS ot_losses
            FROM teams t
            LEFT JOIN games g ON (g.home_team_id=t.team_id OR g.away_team_id=t.team_id)
                              AND g.season_id=:sid AND g.game_status='final'
            WHERE t.season_id = :sid
            GROUP BY t.team_id, t.team_code, t.team_name
            ORDER BY pts DESC, wins DESC
        """), {"sid": SEASON_ID}).fetchall()

        result = []
        for i, r in enumerate(rows):
            status = "playoff" if i < 4 else ("bubble" if i < 6 else "out")
            result.append({
                "name":       r.team_code,
                "logo":       _logo_uri(r.team_code),
                "wins":       int(r.wins or 0),
                "losses":     int(r.losses or 0),
                "ot_losses":  int(r.ot_losses or 0),
                "gp":         int(r.gp or 0),
                "points":     int(r.pts or 0),
                "status":     status,
            })
        return result
    finally:
        session.close()