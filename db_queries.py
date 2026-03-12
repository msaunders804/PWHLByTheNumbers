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

_THIS_DIR   = Path(__file__).resolve().parent   # root dir (db_queries.py lives here)
PLAYERS_DIR = _THIS_DIR / "assets" / "players"

def _player_photo_uri(player_name: str):
    # firstname_lastname.jpg — e.g. rebecca_leslie.jpg
    slug = player_name.lower().replace(" ", "_").replace("-", "_").replace("'", "")
    for ext in ("jpg", "jpeg", "png", "webp"):
        p = PLAYERS_DIR / f"{slug}.{ext}"
        if p.exists():
            return p.resolve().as_uri()
    return None

_env_root   = os.environ.get("BTN_REPO_ROOT", "").strip()
_REPO_ROOT  = Path(_env_root).resolve() if _env_root else _THIS_DIR


import base64 as _b64

def _file_to_data_uri(path: Path) -> str | None:
    """Base64-encode a local file into a data URI — works in Playwright on any OS."""
    if not path.exists():
        return None
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".webp": "image/webp", ".svg": "image/svg+xml"}.get(path.suffix.lower(), "image/png")
    return f"data:{mime};base64,{_b64.b64encode(path.read_bytes()).decode()}"


def _logo_uri(team_code: str) -> str | None:
    name = TEAM_CODE_MAP.get(team_code.upper())
    if not name:
        return None
    return _file_to_data_uri(_REPO_ROOT / "assets" / "logos" / f"{name}.png")


def _pwhl_logo_uri() -> str | None:
    return _file_to_data_uri(_REPO_ROOT / "assets" / "logos" / "PWHL_logo.svg")


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

        # Record as featured
        session.execute(text("""
            INSERT IGNORE INTO featured_players (player_id, featured_date)
            VALUES (:pid, CURDATE())
        """), {"pid": candidates.player_id})
        session.commit()

        return _build_spotlight_dict(candidates, session)

    finally:
        session.close()


def _official_photo_uri(player_id: int, player_name: str = "") -> str | None:
    """
    Returns the official headshot for spotlight use.
    Checks local assets/players/official/{id} first, then CDN.
    Does NOT check candid folder — use _candid_photo_uri() for that.
    """
    official_dir = _THIS_DIR / "assets" / "players" / "official"
    for ext in ["jpg", "jpeg", "png", "webp"]:
        p = official_dir / f"{player_id}.{ext}"
        if p.exists():
            return p.resolve().as_uri()

    return f"https://assets.leaguestat.com/pwhl/240x240/{player_id}.jpg"


def _candid_photo_uri(player_name: str) -> str | None:
    """
    Looks for a candid photo in assets/players/{first}_{last}.{ext}.
    Returns file:// URI if found, None otherwise.
    Used by power rankings and recap — NOT spotlight.
    """
    slug = player_name.lower().replace(" ", "_").replace("-", "_").replace("'", "")
    candid_dir = _THIS_DIR / "assets" / "players"
    for ext in ["jpg", "jpeg", "png", "webp"]:
        p = candid_dir / f"{slug}.{ext}"
        if p.exists():
            return p.resolve().as_uri()
    return None


def _build_spotlight_dict(candidate, session) -> dict:
    """Shared stat builder used by all get_spotlight_player* functions."""
    pid = candidate.player_id

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

    def _rank(metric, col):
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

    toi_row = session.execute(text(
        "SELECT avg_toi_seconds FROM players WHERE player_id = :pid"
    ), {"pid": pid}).fetchone()
    avg_toi_sec = int(toi_row.avg_toi_seconds) if toi_row and toi_row.avg_toi_seconds else None
    toi_str = f"{avg_toi_sec // 60}:{avg_toi_sec % 60:02d}" if avg_toi_sec else "—"

    if avg_toi_sec:
        toi_rank_row = session.execute(text("""
            SELECT COUNT(*) + 1 AS rnk
            FROM players
            WHERE avg_toi_seconds > :val AND avg_toi_seconds IS NOT NULL
        """), {"val": avg_toi_sec}).fetchone()
        toi_rank_str = f"#{toi_rank_row.rnk} in league"
    else:
        toi_rank_str = "—"

    return {
        "player_id":     pid,
        "player_name":   candidate.player_name,
        "player_team":   candidate.team_name,
        "team_logo":     _logo_uri(candidate.team_code),
        "position":      candidate.position or "F",
        "jersey_number": candidate.jersey_number or "—",
        "nationality":   candidate.nationality or "—",
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
        "player_photo":  _official_photo_uri(pid, candidate.player_name),
        "pwhl_logo":     _pwhl_logo_uri(),
        "season_label":  f"Season {SEASON_ID} • {points} PTS",
    }


def get_spotlight_player_by_id(player_id: int) -> dict | None:
    """
    Fetch spotlight data for a specific player by ID.
    Bypasses the random selection and featured_players rotation.
    """
    session = Session()
    try:
        candidate = session.execute(text("""
            SELECT p.player_id,
                   CONCAT(p.first_name, ' ', p.last_name) AS player_name,
                   t.team_name, t.team_code,
                   p.position, p.jersey_number, p.nationality
            FROM players p
            JOIN (
                SELECT s2.player_id, s2.team_id
                FROM player_game_stats s2
                JOIN games g2 ON g2.game_id = s2.game_id
                WHERE g2.season_id = :sid
                GROUP BY s2.player_id, s2.team_id
            ) latest ON latest.player_id = p.player_id
            JOIN teams t ON t.team_id = latest.team_id AND t.season_id = :sid
            WHERE p.player_id = :pid
            LIMIT 1
        """), {"sid": SEASON_ID, "pid": player_id}).fetchone()

        if not candidate:
            return None

        # Reuse the same stat-building logic
        return _build_spotlight_dict(candidate, session)
    finally:
        session.close()


def get_spotlight_player_by_name(name: str) -> dict | None:
    """
    Fetch spotlight data for a specific player by partial name match.
    Case-insensitive. Returns the closest match.
    """
    session = Session()
    try:
        candidate = session.execute(text("""
            SELECT p.player_id,
                   CONCAT(p.first_name, ' ', p.last_name) AS player_name,
                   t.team_name, t.team_code,
                   p.position, p.jersey_number, p.nationality
            FROM players p
            JOIN (
                SELECT s2.player_id, s2.team_id
                FROM player_game_stats s2
                JOIN games g2 ON g2.game_id = s2.game_id
                WHERE g2.season_id = :sid
                GROUP BY s2.player_id, s2.team_id
            ) latest ON latest.player_id = p.player_id
            JOIN teams t ON t.team_id = latest.team_id AND t.season_id = :sid
            WHERE CONCAT(p.first_name, ' ', p.last_name) LIKE :name
            ORDER BY p.last_name
            LIMIT 1
        """), {"sid": SEASON_ID, "name": f"%{name}%"}).fetchone()

        if not candidate:
            return None

        return _build_spotlight_dict(candidate, session)
    finally:
        session.close()


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

def _parse_game_time(raw: str) -> str:
    """
    Normalize whatever the API returns into a readable time string like "7:00 PM ET".
    Handles: "19:00", "7:00 PM", "19:00:00", unix epoch int, blank/None -> "TBD"
    Note: PWHL API times are typically ET.
    """
    import re
    from datetime import datetime as _dt

    if not raw or str(raw).strip() in ("", "0", "00:00", "00:00:00"):
        return "TBD"

    s = str(raw).strip()

    # Unix epoch (numeric string)
    if re.fullmatch(r"\d{9,12}", s):
        try:
            return _dt.utcfromtimestamp(int(s)).strftime("%-I:%M %p ET")
        except Exception:
            return "TBD"

    # Already has AM/PM — just normalise spacing
    if re.search(r"[AaPp][Mm]", s):
        # strip seconds if present: "7:00:00 PM" -> "7:00 PM"
        s = re.sub(r":(\d{2})\s*([AaPp][Mm])", lambda m: f" {m.group(2).upper()}", s)
        s = re.sub(r"\s+", " ", s).strip()
        if "ET" not in s and "CT" not in s:
            s += " ET"
        return s

    # 24-hour "HH:MM" or "HH:MM:SS"
    m = re.match(r"^(\d{1,2}):(\d{2})", s)
    if m:
        h, mn = int(m.group(1)), int(m.group(2))
        if h == 0:
            return "TBD"
        period = "AM" if h < 12 else "PM"
        h12 = h if h <= 12 else h - 12
        if h12 == 0:
            h12 = 12
        return f"{h12}:{mn:02d} {period} ET"

    return "TBD"


def get_upcoming_schedule(start_date, end_date):
    """
    Returns games scheduled between start_date and end_date from the API schedule.
    Uses API directly since only final games are stored in the DB.
    Groups by day for the schedule slide.
    """
    import requests as _req
    from collections import OrderedDict
    from datetime import datetime as _dt

    # Fetch full season schedule from API
    params = {
        "feed": "modulekit", "view": "schedule",
        "season_id": SEASON_ID,
        "key": "446521baf8c38984", "client_code": "pwhl", "fmt": "json"
    }
    resp = _req.get("https://lscluster.hockeytech.com/feed/index.php",
                    params=params, timeout=15)
    resp.raise_for_status()
    schedule = resp.json().get("SiteKit", {}).get("Schedule", [])

    days = OrderedDict()
    for g in schedule:
        try:
            game_date = _dt.strptime(g.get("date_played", ""), "%Y-%m-%d").date()
        except ValueError:
            continue

        if not (start_date <= game_date <= end_date):
            continue

        # DEBUG: uncomment to see raw API fields for time diagnosis
        # import json as _j; print(_j.dumps({k:v for k,v in g.items() if "time" in k.lower() or "start" in k.lower() or "network" in k.lower()}))

        # Skip completed games
        is_final = (
            str(g.get("game_status", "")).lower() == "final"
            or str(g.get("status", "")) == "4"
            or str(g.get("final", "0")) == "1"
        )
        if is_final:
            continue

        home_code = g.get("home_team_code", g.get("home_team_name", "")[:3].upper())
        away_code = g.get("visiting_team_code", g.get("visiting_team_name", "")[:3].upper())

        # Parse game time — API may return "19:00", "7:00 PM", epoch int, or be absent
        raw_time = (g.get("game_time") or g.get("start_time") or
                    g.get("time") or g.get("scheduled_time") or "")
        game_time = _parse_game_time(raw_time)

        d = str(game_date)
        if d not in days:
            days[d] = {
                "day_name": game_date.strftime("%A").upper(),
                "date_str": game_date.strftime("%b %d").upper(),
                "games": []
            }
        days[d]["games"].append({
            "game_id":   g.get("id"),
            "away_team": away_code,
            "home_team": home_code,
            "away_logo": _logo_uri(away_code),
            "home_logo": _logo_uri(home_code),
            "time":      game_time,
            "broadcast": g.get("network", "") or "",
        })

    return list(days.values())


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

        # Upcoming games this week — fetch from API since only finals are in DB
        import requests as _req
        from datetime import datetime as _dt2
        api_params = {
            "feed": "modulekit", "view": "schedule", "season_id": SEASON_ID,
            "key": "446521baf8c38984", "client_code": "pwhl", "fmt": "json"
        }
        api_schedule = _req.get("https://lscluster.hockeytech.com/feed/index.php",
                                 params=api_params, timeout=15).json()
        raw_games = api_schedule.get("SiteKit", {}).get("Schedule", [])

        # Build a simple game list with team IDs for scoring
        # Use a reverse lookup: team_code -> team_id from standings data
        code_to_id = {v: k for k, v in code_map.items()}

        class _Game:
            def __init__(self, gid, date, home_id, away_id, game_time):
                self.game_id      = gid
                self.date         = date
                self.home_team_id = home_id
                self.away_team_id = away_id
                self.game_time    = game_time

        games = []
        for g in raw_games:
            try:
                gdate = _dt2.strptime(g.get("date_played", ""), "%Y-%m-%d").date()
            except ValueError:
                continue
            if not (start_date <= gdate <= end_date):
                continue
            is_final = (
                str(g.get("game_status","")).lower() == "final"
                or str(g.get("status","")) == "4"
                or str(g.get("final","0")) == "1"
            )
            if is_final:
                continue
            h_code = g.get("home_team_code", "")
            a_code = g.get("visiting_team_code", "")
            h_id   = int(g.get("home_team", 0)) or code_to_id.get(h_code)
            a_id   = int(g.get("visiting_team", 0)) or code_to_id.get(a_code)
            if h_id and a_id:
                games.append(_Game(g.get("id"), gdate, h_id, a_id,
                                   _parse_game_time(g.get("game_time") or g.get("start_time") or "")))

        if not games:
            return None

        # Score each game
        best_game = None
        best_score = -1
        for g in games:
            h, a = g.home_team_id, g.away_team_id
            rank_diff    = abs(rank_map.get(h, 8) - rank_map.get(a, 8))
            combined_pts = pts_map.get(h, 0) + pts_map.get(a, 0)
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
            "gtw_time":       best_game.game_time,
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
                   SUM(CASE WHEN g.result_type='OT'
                             AND ((g.home_team_id=t.team_id AND g.home_score<g.away_score) OR
                                  (g.away_team_id=t.team_id AND g.away_score<g.home_score))
                            THEN 1 ELSE 0 END) AS otl,
                   SUM(CASE WHEN g.result_type='SO'
                             AND ((g.home_team_id=t.team_id AND g.home_score<g.away_score) OR
                                  (g.away_team_id=t.team_id AND g.away_score<g.home_score))
                            THEN 1 ELSE 0 END) AS sol,
                   SUM(CASE WHEN g.result_type='OT'
                             AND ((g.home_team_id=t.team_id AND g.home_score>g.away_score) OR
                                  (g.away_team_id=t.team_id AND g.away_score>g.home_score))
                            THEN 1 ELSE 0 END) AS otw,
                   /* home splits */
                   SUM(CASE WHEN g.home_team_id=t.team_id AND g.home_score>g.away_score THEN 1 ELSE 0 END) AS hw,
                   SUM(CASE WHEN g.home_team_id=t.team_id AND g.home_score<g.away_score AND g.result_type='REG' THEN 1 ELSE 0 END) AS hl,
                   SUM(CASE WHEN g.home_team_id=t.team_id AND g.result_type IN ('OT','SO') AND g.home_score<g.away_score THEN 1 ELSE 0 END) AS hotl,
                   /* away splits */
                   SUM(CASE WHEN g.away_team_id=t.team_id AND g.away_score>g.home_score THEN 1 ELSE 0 END) AS aw,
                   SUM(CASE WHEN g.away_team_id=t.team_id AND g.away_score<g.home_score AND g.result_type='REG' THEN 1 ELSE 0 END) AS al,
                   SUM(CASE WHEN g.away_team_id=t.team_id AND g.result_type IN ('OT','SO') AND g.away_score<g.home_score THEN 1 ELSE 0 END) AS aotl
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
                "name":         r.team_code,
                "abbr":         r.team_code,
                "logo":         _logo_uri(r.team_code),
                "wins":         int(r.wins or 0),
                "losses":       int(r.losses or 0),
                "ot_losses":    int((r.otl or 0) + (r.sol or 0)),
                "otw":          int(r.otw or 0),
                "otl":          int((r.otl or 0) + (r.sol or 0)),
                "gp":           int(r.gp or 0),
                "points":       int(r.pts or 0),
                "status":       status,
                "home_record":  f"{int(r.hw or 0)}-{int(r.hl or 0)}-{int(r.hotl or 0)}",
                "away_record":  f"{int(r.aw or 0)}-{int(r.al or 0)}-{int(r.aotl or 0)}",
            })
        return result
    finally:
        session.close()


# ── Power Rankings ──────────────────────────────────────────────────────────────

def get_power_rankings() -> list[dict]:
    """
    Compute power rankings weighted toward current form (win streak).

    Score = (streak_points * 3) + (ppg * 20) + (last5_gd * 1.5)

    streak_points:
      positive streak  → +N  (win streak)
      negative streak  → -N  (loss streak)
    ppg:    season points per game
    last5_gd: goal differential in last 5 games
    """
    session = Session()
    try:
        rows = session.execute(text("""
            SELECT
                t.team_id, t.team_code,
                COUNT(g.game_id)                                       AS gp,
                SUM(CASE
                    WHEN (g.home_team_id=t.team_id AND g.home_score>g.away_score) OR
                         (g.away_team_id=t.team_id AND g.away_score>g.home_score) THEN 2
                    WHEN g.result_type IN ('OT','SO') AND (
                         (g.home_team_id=t.team_id AND g.home_score<g.away_score) OR
                         (g.away_team_id=t.team_id AND g.away_score<g.home_score)) THEN 1
                    ELSE 0 END)                                        AS pts,
                SUM(CASE
                    WHEN g.home_team_id=t.team_id THEN g.home_score - g.away_score
                    ELSE g.away_score - g.home_score END)              AS season_gd
            FROM teams t
            LEFT JOIN games g ON (g.home_team_id=t.team_id OR g.away_team_id=t.team_id)
                              AND g.season_id=:sid AND g.game_status='final'
            WHERE t.season_id=:sid
            GROUP BY t.team_id, t.team_code
        """), {"sid": SEASON_ID}).fetchall()

        # Last 5 games per team — computed in Python to avoid complex SQL
        last5_map = {tid: {"last5_gd": 0, "last5_wins": 0} for tid in [r.team_id for r in rows]}

        # Win/loss streak per team
        streak_map = {}
        all_games = session.execute(text("""
            SELECT g.game_id, g.date,
                   g.home_team_id, g.away_team_id,
                   g.home_score, g.away_score, g.result_type
            FROM games g
            WHERE g.season_id=:sid AND g.game_status='final'
            ORDER BY g.date DESC, g.game_id DESC
        """), {"sid": SEASON_ID}).fetchall()

        team_ids = [r.team_id for r in rows]
        for tid in team_ids:
            streak = 0
            team_games = [g for g in all_games
                          if g.home_team_id == tid or g.away_team_id == tid]
            # Last 5 goal differential
            for g in team_games[:5]:
                won = ((g.home_team_id == tid and g.home_score > g.away_score) or
                       (g.away_team_id == tid and g.away_score > g.home_score))
                gd = (g.home_score - g.away_score) if g.home_team_id == tid else (g.away_score - g.home_score)
                last5_map[tid]["last5_gd"]   += gd
                last5_map[tid]["last5_wins"]  += 1 if won else 0
            # Streak
            for g in team_games:
                won = ((g.home_team_id == tid and g.home_score > g.away_score) or
                       (g.away_team_id == tid and g.away_score > g.home_score))
                if streak == 0:
                    streak = 1 if won else -1
                elif (streak > 0 and won) or (streak < 0 and not won):
                    streak += (1 if won else -1)
                else:
                    break
            streak_map[tid] = streak

        # Build ranked list
        rankings = []
        for r in rows:
            gp  = int(r.gp or 0)
            pts = int(r.pts or 0)
            ppg = round(pts / gp, 3) if gp else 0
            l5  = last5_map.get(r.team_id, {"last5_gd": 0, "last5_wins": 0})
            streak = streak_map.get(r.team_id, 0)

            score = (streak * 3) + (ppg * 20) + (l5["last5_gd"] * 1.5)

            rankings.append({
                "team_code":   r.team_code,
                "logo":        _logo_uri(r.team_code),
                "gp":          gp,
                "pts":         pts,
                "ppg":         ppg,
                "season_gd":   int(r.season_gd or 0),
                "last5_gd":    l5["last5_gd"],
                "last5_wins":  l5["last5_wins"],
                "streak":      streak,
                "score":       score,
            })

        rankings.sort(key=lambda x: x["score"], reverse=True)

        # Assign ranks and movement labels
        for i, team in enumerate(rankings):
            team["rank"] = i + 1
            s = team["streak"]
            team["streak_label"] = f"W{s}" if s > 0 else (f"L{abs(s)}" if s < 0 else "—")
            team["streak_hot"]   = s >= 3   # on fire
            team["streak_cold"]  = s <= -3  # struggling

        return rankings

    finally:
        session.close()


# ── Hot Player (for Power Rankings slide 3) ─────────────────────────────────────

def get_hot_player() -> dict | None:
    """
    Finds the hottest skater right now: most points in last 5 games.
    Returns full player card with season stats, last-5 stats, and photo.
    """
    session = Session()
    try:
        # Get last 5 game IDs per player and sum their points
        hot = session.execute(text("""
            SELECT
                s.player_id,
                CONCAT(p.first_name, ' ', p.last_name) AS player_name,
                t.team_code,
                t.team_name,
                p.position,
                p.jersey_number,
                SUM(s.goals + s.assists)               AS last5_pts,
                SUM(s.goals)                            AS last5_goals,
                SUM(s.assists)                          AS last5_assists
            FROM player_game_stats s
            JOIN players p ON p.player_id = s.player_id
            JOIN games g ON g.game_id = s.game_id
            JOIN teams t ON t.team_id = s.team_id AND t.season_id = :sid
            WHERE g.season_id = :sid
              AND g.game_status = 'final'
              AND (p.position IS NULL OR p.position != 'G')
              AND g.game_id IN (
                  SELECT game_id FROM (
                      SELECT gs2.game_id,
                             ROW_NUMBER() OVER (
                                 PARTITION BY gs2.player_id
                                 ORDER BY g2.date DESC, g2.game_id DESC
                             ) AS rn
                      FROM player_game_stats gs2
                      JOIN games g2 ON g2.game_id = gs2.game_id
                      WHERE g2.season_id = :sid AND g2.game_status = 'final'
                        AND gs2.player_id = s.player_id
                  ) recent
                  WHERE rn <= 5
              )
            GROUP BY s.player_id, player_name, t.team_code, t.team_name,
                     p.position, p.jersey_number
            ORDER BY last5_pts DESC, last5_goals DESC
            LIMIT 1
        """), {"sid": SEASON_ID}).fetchone()

        if not hot:
            return None

        pid = hot.player_id

        # Full season stats
        season = session.execute(text("""
            SELECT SUM(s.goals)   AS goals,
                   SUM(s.assists) AS assists,
                   SUM(s.shots)   AS shots,
                   COUNT(DISTINCT s.game_id) AS gp
            FROM player_game_stats s
            JOIN games g ON g.game_id = s.game_id
            WHERE s.player_id = :pid AND g.season_id = :sid
              AND g.game_status = 'final'
        """), {"pid": pid, "sid": SEASON_ID}).fetchone()

        goals   = int(season.goals or 0)
        assists = int(season.assists or 0)
        gp      = int(season.gp or 1)

        # League rank for points
        pts_rank = session.execute(text("""
            SELECT COUNT(*) + 1 AS rnk
            FROM (
                SELECT player_id, SUM(goals + assists) AS val
                FROM player_game_stats s2
                JOIN games g2 ON g2.game_id = s2.game_id
                WHERE g2.season_id = :sid AND g2.game_status = 'final'
                GROUP BY player_id
            ) ranked
            WHERE val > :v
        """), {"sid": SEASON_ID, "v": goals + assists}).fetchone()

        # avg TOI
        toi_row = session.execute(text(
            "SELECT avg_toi_seconds FROM players WHERE player_id = :pid"
        ), {"pid": pid}).fetchone()
        avg_toi_sec = int(toi_row.avg_toi_seconds) if toi_row and toi_row.avg_toi_seconds else None
        toi_str = f"{avg_toi_sec // 60}:{avg_toi_sec % 60:02d}" if avg_toi_sec else "—"

        return {
            "player_id":      pid,
            "player_name":    hot.player_name,
            "team_code":      hot.team_code,
            "team_name":      hot.team_name,
            "team_logo":      _logo_uri(hot.team_code),
            "position":       hot.position or "F",
            "jersey_number":  hot.jersey_number or "",
            "player_photo":   _candid_photo_uri(hot.player_name) or f"https://assets.leaguestat.com/pwhl/240x240/{pid}.jpg",
            # Last 5
            "last5_pts":      int(hot.last5_pts or 0),
            "last5_goals":    int(hot.last5_goals or 0),
            "last5_assists":  int(hot.last5_assists or 0),
            # Season
            "season_goals":   goals,
            "season_assists": assists,
            "season_pts":     goals + assists,
            "season_gp":      gp,
            "pts_rank":       int(pts_rank.rnk) if pts_rank else "—",
            "toi":            toi_str,
        }

    finally:
        session.close()


# ── Offensive vs Defensive Breakdown ───────────────────────────────────────────

def get_offense_defense_breakdown() -> list[dict]:
    """
    Returns GF/GA per game for each team, plus archetype label.
    Quadrants:
      High GF + Low GA  → ELITE
      High GF + High GA → OFFENSIVE CHAOS
      Low GF  + Low GA  → DEFENSIVE SHELL
      Low GF  + High GA → REBUILDING
    """
    session = Session()
    try:
        rows = session.execute(text("""
            SELECT
                t.team_id, t.team_code,
                COUNT(g.game_id) AS gp,
                SUM(CASE WHEN g.home_team_id=t.team_id THEN g.home_score
                         ELSE g.away_score END) AS gf,
                SUM(CASE WHEN g.home_team_id=t.team_id THEN g.away_score
                         ELSE g.home_score END) AS ga
            FROM teams t
            JOIN games g ON (g.home_team_id=t.team_id OR g.away_team_id=t.team_id)
                         AND g.season_id=:sid AND g.game_status='final'
            WHERE t.season_id=:sid
            GROUP BY t.team_id, t.team_code
        """), {"sid": SEASON_ID}).fetchall()

        teams = []
        for r in rows:
            gp = int(r.gp or 1)
            gf = int(r.gf or 0)
            ga = int(r.ga or 0)
            gfpg = round(gf / gp, 2)
            gapg = round(ga / gp, 2)
            teams.append({
                "team_code": r.team_code,
                "logo":      _logo_uri(r.team_code),
                "gp":        gp,
                "gf":        gf,
                "ga":        ga,
                "gfpg":      gfpg,
                "gapg":      gapg,
            })

        # League averages for quadrant lines
        avg_gfpg = round(sum(t["gfpg"] for t in teams) / len(teams), 2)
        avg_gapg = round(sum(t["gapg"] for t in teams) / len(teams), 2)

        archetypes = {
            (True,  True):  ("ELITE",            "#5e17eb"),
            (True,  False): ("OFFENSIVE",         "#f5a623"),
            (False, True):  ("DEFENSIVE",         "#2a9d3a"),
            (False, False): ("STRUGGLING",        "#c0392b"),
        }

        for t in teams:
            high_gf = t["gfpg"] >= avg_gfpg
            low_ga  = t["gapg"] <= avg_gapg
            label, color = archetypes[(high_gf, low_ga)]
            t["archetype"]       = label
            t["archetype_color"] = color

        return {
            "teams":    teams,
            "avg_gfpg": avg_gfpg,
            "avg_gapg": avg_gapg,
        }

    finally:
        session.close()


# ── Monte Carlo Simulation Inputs ─────────────────────────────────────────────

def get_remaining_schedule() -> list[dict]:
    """
    Returns all unplayed games remaining in the current season.
    Used as the simulation game list for Monte Carlo.
    """
    session = Session()
    try:
        rows = session.execute(text("""
            SELECT
                g.game_id,
                g.date,
                g.home_team_id,
                g.away_team_id,
                ht.team_code AS home_code,
                at.team_code AS away_code
            FROM games g
            JOIN teams ht ON ht.team_id = g.home_team_id AND ht.season_id = :sid
            JOIN teams at ON at.team_id = g.away_team_id AND at.season_id = :sid
            WHERE g.season_id    = :sid
              AND g.game_status != 'final'
            ORDER BY g.date ASC, g.game_id ASC
        """), {"sid": SEASON_ID}).fetchall()

        return [{
            "game_id":      r.game_id,
            "date":         str(r.date),
            "home_team_id": r.home_team_id,
            "away_team_id": r.away_team_id,
            "home_code":    r.home_code,
            "away_code":    r.away_code,
        } for r in rows]
    finally:
        session.close()


def get_simulation_inputs() -> dict[int, dict]:
    """
    Returns per-team inputs needed to calculate win probability in Monte Carlo.

    Inputs per team:
      - pts_pct       : season points / (games played * 2)
      - rank_score    : raw power ranking score (streak*3 + ppg*20 + last5_gd*1.5)
      - last5_gd      : goal differential in last 5 games
      - home_win_pct  : wins at home / home games played
      - team_code     : abbreviation
      - gp            : games played
      - pts           : current points
      - games_remaining: count of unplayed games

    Returns dict keyed by team_id.
    """
    session = Session()
    try:
        # Season stats + home record
        rows = session.execute(text("""
            WITH results AS (
                SELECT
                    g.home_team_id                                          AS team_id,
                    CASE WHEN g.home_score > g.away_score THEN 1 ELSE 0 END AS win,
                    CASE WHEN g.home_score < g.away_score
                          AND g.result_type = 'OT'                          THEN 1 ELSE 0 END AS otl,
                    CASE WHEN g.home_score < g.away_score
                          AND g.result_type = 'SO'                          THEN 1 ELSE 0 END AS sol,
                    g.home_score - g.away_score                             AS gd,
                    'home'                                                  AS venue
                FROM games g
                WHERE g.season_id = :sid AND g.game_status = 'final'

                UNION ALL

                SELECT
                    g.away_team_id,
                    CASE WHEN g.away_score > g.home_score THEN 1 ELSE 0 END,
                    CASE WHEN g.away_score < g.home_score
                          AND g.result_type = 'OT'                          THEN 1 ELSE 0 END,
                    CASE WHEN g.away_score < g.home_score
                          AND g.result_type = 'SO'                          THEN 1 ELSE 0 END,
                    g.away_score - g.home_score,
                    'away'
                FROM games g
                WHERE g.season_id = :sid AND g.game_status = 'final'
            )
            SELECT
                t.team_id,
                t.team_code,
                COUNT(*)                                                    AS gp,
                SUM(win)*2 + SUM(otl) + SUM(sol)                           AS pts,
                SUM(CASE WHEN venue='home' AND win=1 THEN 1 ELSE 0 END)    AS home_wins,
                SUM(CASE WHEN venue='home'           THEN 1 ELSE 0 END)    AS home_gp
            FROM results r
            JOIN teams t ON t.team_id = r.team_id AND t.season_id = :sid
            GROUP BY t.team_id, t.team_code
        """), {"sid": SEASON_ID}).fetchall()

        # All completed games for last-5 and streak (reuse power rankings logic)
        all_games = session.execute(text("""
            SELECT game_id, date, home_team_id, away_team_id,
                   home_score, away_score, result_type
            FROM games
            WHERE season_id = :sid AND game_status = 'final'
            ORDER BY date DESC, game_id DESC
        """), {"sid": SEASON_ID}).fetchall()

        # Remaining games count per team
        remaining_rows = session.execute(text("""
            SELECT home_team_id AS team_id, COUNT(*) AS cnt
            FROM games
            WHERE season_id = :sid AND game_status != 'final'
            GROUP BY home_team_id

            UNION ALL

            SELECT away_team_id, COUNT(*)
            FROM games
            WHERE season_id = :sid AND game_status != 'final'
            GROUP BY away_team_id
        """), {"sid": SEASON_ID}).fetchall()

        remaining_map: dict[int, int] = {}
        for r in remaining_rows:
            remaining_map[r.team_id] = remaining_map.get(r.team_id, 0) + r.cnt

        team_ids = [r.team_id for r in rows]
        result   = {}

        for r in rows:
            tid = r.team_id
            gp  = int(r.gp  or 0)
            pts = int(r.pts or 0)

            # Points percentage
            pts_pct = pts / (gp * 2) if gp else 0.0

            # Home win %
            home_gp   = int(r.home_gp   or 0)
            home_wins = int(r.home_wins or 0)
            home_win_pct = home_wins / home_gp if home_gp else 0.5

            # Last 5 GD and streak
            team_games = [g for g in all_games
                          if g.home_team_id == tid or g.away_team_id == tid]

            last5_gd = 0
            for g in team_games[:5]:
                last5_gd += (g.home_score - g.away_score) if g.home_team_id == tid \
                             else (g.away_score - g.home_score)

            streak = 0
            for g in team_games:
                won = ((g.home_team_id == tid and g.home_score > g.away_score) or
                       (g.away_team_id == tid and g.away_score > g.home_score))
                if streak == 0:
                    streak = 1 if won else -1
                elif (streak > 0 and won) or (streak < 0 and not won):
                    streak += (1 if won else -1)
                else:
                    break

            ppg = (pts / gp) if gp else 0.0
            rank_score = (streak * 3) + (ppg * 20) + (last5_gd * 1.5)

            result[tid] = {
                "team_id":          tid,
                "team_code":        r.team_code,
                "gp":               gp,
                "pts":              pts,
                "pts_pct":          round(pts_pct, 4),
                "home_win_pct":     round(home_win_pct, 4),
                "last5_gd":         last5_gd,
                "rank_score":       round(rank_score, 4),
                "games_remaining":  remaining_map.get(tid, 0),
            }

        return result

    finally:
        session.close()
