"""
gsaa.py — Goals Saved Above Average analytics.

"The Goalie Carrying Her Team"

Core metrics:
  - League average SV%
  - Season GSAA per goalie (goals saved vs what an average goalie would allow)
  - Per-game GSAA log (for sparkline / trend chart)
  - Stolen games: wins where the goalie outperformed while her team bled shots
  - Standings leverage: was the win meaningful in the standings race?

GSAA formula:
    league_avg_sv% = SUM(all_saves) / SUM(all_shots_against)    [qualified games only]
    game_gsaa      = saves - (shots_against × league_avg_sv%)
    season_gsaa    = SUM(game_gsaa)

Minimum qualifier: 600 minutes played for season leaderboard.
"""

from __future__ import annotations
from sqlalchemy import text
from pwhl_btn.db.db_config import get_engine

SEASON_ID   = 8
MIN_MINUTES = 600   # ~10 full games to qualify for season leaderboard


# ── League average SV% ────────────────────────────────────────────────────────

def get_league_avg_sv_pct(conn, season_id: int = SEASON_ID) -> float:
    row = conn.execute(text("""
        SELECT SUM(s.saves)         AS total_saves,
               SUM(s.shots_against) AS total_shots
        FROM goalie_game_stats s
        JOIN games g ON g.game_id = s.game_id
        WHERE g.season_id   = :sid
          AND g.game_status = 'final'
          AND s.minutes_played >= 55        -- exclude garbage-time appearances
    """), {"sid": season_id}).fetchone()
    if not row or not row.total_shots:
        return 0.910  # fallback
    return row.total_saves / row.total_shots


# ── Season GSAA leaderboard ───────────────────────────────────────────────────

def get_season_gsaa(season_id: int = SEASON_ID) -> list[dict]:
    """
    Returns all qualified goalies ranked by season GSAA.
    Qualifier: MIN_MINUTES minutes played.
    """
    engine = get_engine(pool_pre_ping=True)
    with engine.connect() as conn:
        league_sv = get_league_avg_sv_pct(conn, season_id)

        rows = conn.execute(text("""
            SELECT
                s.player_id,
                CONCAT(p.first_name, ' ', p.last_name)   AS name,
                t.team_code,
                COUNT(DISTINCT s.game_id)                 AS gp,
                SUM(s.minutes_played) / 60.0              AS minutes,
                SUM(s.shots_against)                      AS sa,
                SUM(s.saves)                              AS sv,
                SUM(s.goals_against)                      AS ga,
                ROUND(SUM(s.saves) /
                      NULLIF(SUM(s.shots_against), 0), 4) AS sv_pct,
                ROUND(SUM(s.goals_against) /
                      NULLIF(SUM(s.minutes_played) / 3600.0, 0), 2) AS gaa,
                SUM(CASE WHEN s.decision = 'W'  THEN 1 ELSE 0 END)  AS wins,
                SUM(CASE WHEN s.goals_against = 0
                          AND s.minutes_played >= 3300    -- 55 min
                         THEN 1 ELSE 0 END)               AS shutouts
            FROM goalie_game_stats s
            JOIN players p ON p.player_id = s.player_id
            JOIN teams   t ON t.team_id   = s.team_id AND t.season_id = :sid
            JOIN games   g ON g.game_id   = s.game_id
            WHERE g.season_id   = :sid
              AND g.game_status = 'final'
              AND s.minutes_played >= 55
            GROUP BY s.player_id, p.first_name, p.last_name, t.team_code
            HAVING SUM(s.minutes_played) >= :min_min
            ORDER BY sa DESC
        """), {"sid": season_id, "min_min": MIN_MINUTES * 60}).mappings().all()

    result = []
    for r in rows:
        sa   = float(r["sa"] or 0)
        sv   = float(r["sv"] or 0)
        gsaa = round(sv - (sa * league_sv), 2)
        result.append({**dict(r), "gsaa": gsaa, "league_avg_sv_pct": round(league_sv, 4)})

    result.sort(key=lambda x: x["gsaa"], reverse=True)
    return result


# ── Per-game GSAA log ─────────────────────────────────────────────────────────

def get_goalie_game_log(player_id: int, season_id: int = SEASON_ID) -> list[dict]:
    """
    Per-game stats + GSAA for a single goalie, ordered by date.
    Used for sparkline / trend chart.
    """
    engine = get_engine(pool_pre_ping=True)
    with engine.connect() as conn:
        league_sv = get_league_avg_sv_pct(conn, season_id)

        rows = conn.execute(text("""
            SELECT
                g.game_id,
                g.date,
                opp.team_code                              AS opponent,
                CASE WHEN s.team_id = g.home_team_id
                     THEN 'Home' ELSE 'Away' END           AS home_away,
                s.shots_against,
                s.saves,
                s.goals_against,
                s.minutes_played,
                ROUND(s.saves /
                      NULLIF(s.shots_against, 0), 4)       AS game_sv_pct,
                s.decision,
                g.result_type
            FROM goalie_game_stats s
            JOIN games   g   ON g.game_id   = s.game_id
            JOIN teams   opp ON opp.team_id = CASE
                                    WHEN s.team_id = g.home_team_id
                                    THEN g.away_team_id
                                    ELSE g.home_team_id END
                             AND opp.season_id = g.season_id
            WHERE g.season_id     = :sid
              AND g.game_status   = 'final'
              AND s.player_id     = :pid
              AND s.minutes_played >= 55
            ORDER BY g.date, g.game_id
        """), {"sid": season_id, "pid": player_id}).mappings().all()

    result = []
    for r in rows:
        sa   = float(r["shots_against"] or 0)
        sv   = float(r["saves"] or 0)
        gsaa = round(sv - (sa * league_sv), 2)
        d    = r["date"]
        date_str = d.strftime("%b {day}, %Y").replace("{day}", str(d.day)) if hasattr(d, "strftime") else str(d)
        result.append({**dict(r), "gsaa": gsaa, "date_str": date_str})

    return result


# ── Stolen games ─────────────────────────────────────────────────────────────

def get_stolen_games(player_id: int, season_id: int = SEASON_ID) -> list[dict]:
    """
    Games where the goalie 'stole' the win:
      - Team won
      - Shots against >= 110% of the team's own season average
      - Goalie's game SV% > league average SV%

    Returns games ordered by descending game GSAA.
    """
    game_log = get_goalie_game_log(player_id, season_id)

    engine = get_engine(pool_pre_ping=True)
    with engine.connect() as conn:
        # Team average shots against per game for this goalie's team
        avg_row = conn.execute(text("""
            SELECT AVG(s.shots_against) AS avg_sa
            FROM goalie_game_stats s
            JOIN games g ON g.game_id = s.game_id
            WHERE g.season_id   = :sid
              AND g.game_status = 'final'
              AND s.player_id   = :pid
              AND s.minutes_played >= 55
        """), {"sid": season_id, "pid": player_id}).fetchone()

    team_avg_sa   = float(avg_row.avg_sa or 0) if avg_row else 0
    league_sv     = game_log[0]["league_avg_sv_pct"] if game_log else 0.910
    stolen_thresh = team_avg_sa * 1.10  # 10% above team avg = defense broke down

    stolen = []
    for g in game_log:
        if (g["decision"] == "W"
                and float(g["shots_against"]) >= stolen_thresh
                and float(g["game_sv_pct"] or 0) > league_sv):
            stolen.append({**g, "team_avg_sa": round(team_avg_sa, 1)})

    stolen.sort(key=lambda x: x["gsaa"], reverse=True)
    return stolen


# ── Rolling standings ─────────────────────────────────────────────────────────

def get_standings_at_date(target_date, season_id: int = SEASON_ID) -> list[dict]:
    """
    Compute the standings (points, GP, W, L, OTL) as of a specific date.
    Returns list of team dicts sorted by points desc.
    """
    engine = get_engine(pool_pre_ping=True)
    with engine.connect() as conn:
        rows = conn.execute(text("""
            WITH team_results AS (
                SELECT home_team_id AS team_id,
                       CASE WHEN home_score > away_score THEN 2
                            WHEN result_type IN ('OT','SO') THEN 0
                            ELSE 0 END                AS pts,
                       CASE WHEN home_score > away_score THEN 1 ELSE 0 END AS win,
                       CASE WHEN home_score < away_score
                             AND result_type = 'REG'   THEN 1 ELSE 0 END   AS loss,
                       CASE WHEN home_score < away_score
                             AND result_type IN ('OT','SO') THEN 1 ELSE 0 END AS otl
                FROM games
                WHERE season_id = :sid AND game_status = 'final' AND date <= :dt

                UNION ALL

                SELECT away_team_id AS team_id,
                       CASE WHEN away_score > home_score THEN 2
                            WHEN result_type IN ('OT','SO') THEN 1
                            ELSE 0 END                AS pts,
                       CASE WHEN away_score > home_score THEN 1 ELSE 0 END AS win,
                       CASE WHEN away_score < home_score
                             AND result_type = 'REG'   THEN 1 ELSE 0 END   AS loss,
                       CASE WHEN away_score < home_score
                             AND result_type IN ('OT','SO') THEN 1 ELSE 0 END AS otl
                FROM games
                WHERE season_id = :sid AND game_status = 'final' AND date <= :dt
            )
            SELECT t.team_code,
                   COUNT(*)       AS gp,
                   SUM(tr.win)    AS wins,
                   SUM(tr.loss)   AS losses,
                   SUM(tr.otl)    AS otl,
                   SUM(tr.pts)    AS points
            FROM team_results tr
            JOIN teams t ON t.team_id = tr.team_id AND t.season_id = :sid
            GROUP BY t.team_code
            ORDER BY points DESC, wins DESC
        """), {"sid": season_id, "dt": target_date}).mappings().all()

    return [dict(r) for r in rows]


def get_standings_position(team_code: str, target_date, season_id: int = SEASON_ID) -> int | None:
    """Returns 1-based standings position for a team on a given date."""
    standings = get_standings_at_date(target_date, season_id)
    for i, row in enumerate(standings, start=1):
        if row["team_code"] == team_code:
            return i
    return None


# ── High-leverage game detection ─────────────────────────────────────────────

def get_high_leverage_wins(player_id: int, season_id: int = SEASON_ID) -> list[dict]:
    """
    Wins that were meaningful in the standings race:
      - Team was in positions 3-6 (playoff bubble) on game date
      - Opponent was within 4 points in the standings
      - Goalie GSAA > 0 in that game

    Returns games with pre-game and post-game standings context.
    """
    game_log = get_goalie_game_log(player_id, season_id)
    wins     = [g for g in game_log if g["decision"] == "W" and g["gsaa"] > 0]

    # Get the goalie's team code
    engine = get_engine(pool_pre_ping=True)
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT t.team_code
            FROM goalie_game_stats s
            JOIN teams t ON t.team_id = s.team_id AND t.season_id = :sid
            WHERE s.player_id = :pid
            LIMIT 1
        """), {"sid": season_id, "pid": player_id}).fetchone()

    if not row:
        return []
    team_code = row.team_code

    leverage_games = []
    for g in wins:
        standings = get_standings_at_date(g["date"], season_id)
        pos_map   = {s["team_code"]: (i + 1, s["points"]) for i, s in enumerate(standings)}

        if team_code not in pos_map:
            continue
        team_pos, team_pts = pos_map[team_code]
        opp_pos,  opp_pts  = pos_map.get(g["opponent"], (None, None))

        # Playoff bubble: positions 3-6, or opponent within 4 pts
        pt_gap = abs(team_pts - opp_pts) if opp_pts is not None else 99
        is_bubble   = 2 <= team_pos <= 7
        is_rivalry  = pt_gap <= 4
        if not (is_bubble or is_rivalry):
            continue

        leverage_games.append({
            **g,
            "team_code":     team_code,
            "team_position": team_pos,
            "team_points":   team_pts,
            "opp_position":  opp_pos,
            "opp_points":    opp_pts,
            "points_gap":    pt_gap,
        })

    leverage_games.sort(key=lambda x: x["gsaa"], reverse=True)
    return leverage_games


# ── Top carrier ───────────────────────────────────────────────────────────────

def find_top_carrier(season_id: int = SEASON_ID) -> dict | None:
    """
    Identifies the goalie most 'carrying her team' right now:
    Ranked by a composite: (season GSAA × 0.5) + (stolen_game_count × 1.5) + (leverage_win_count × 2)
    Returns the full data package for that goalie.
    """
    leaderboard = get_season_gsaa(season_id)
    if not leaderboard:
        return None

    best_score  = -999
    best_goalie = None
    best_data   = {}

    for g in leaderboard:
        pid      = g["player_id"]
        stolen   = get_stolen_games(pid, season_id)
        leverage = get_high_leverage_wins(pid, season_id)
        game_log = get_goalie_game_log(pid, season_id)

        score = (g["gsaa"] * 0.5) + (len(stolen) * 1.5) + (len(leverage) * 2.0)
        if score > best_score:
            best_score  = score
            best_goalie = g
            best_data   = {
                "season_stats":    g,
                "game_log":        game_log,
                "stolen_games":    stolen,
                "leverage_wins":   leverage,
                "carrier_score":   round(score, 2),
            }

    return best_data
