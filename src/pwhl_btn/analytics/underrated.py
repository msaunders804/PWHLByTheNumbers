"""
underrated.py — "The Most Underrated Player Nobody Talks About"

Identifies the top 3 underrated skaters (non-MIN) using a composite score:

  UNDERRATED SCORE = (P/60 z-score × 0.35)
                   + (shot volume z-score × 0.20)
                   + (shooting pct z-score × 0.20)
                   + (plus/minus per game z-score × 0.15)
                   + (obscurity bonus × 0.10)

Obscurity bonus:
  +1.0 if NOT team's top scorer
  +0.5 if team is outside top-2 in standings

P/60 uses avg_toi_seconds from players table (season average proxy).
Minimum qualifier: 10 GP, position != 'G'.
Excluded: all MIN players.
"""

from __future__ import annotations
import statistics
from sqlalchemy import text
from pwhl_btn.db.db_config import get_engine

SEASON_ID    = 8
MIN_GP       = 10
EXCLUDE_TEAM = "MIN"


# ── Raw data fetch ─────────────────────────────────────────────────────────────

def _fetch_skater_stats(conn, season_id: int) -> list[dict]:
    rows = conn.execute(text("""
        SELECT
            pgs.player_id,
            CONCAT(p.first_name, ' ', p.last_name) AS name,
            p.position,
            p.avg_toi_seconds,
            t.team_code,
            t.team_id,
            COUNT(DISTINCT pgs.game_id)             AS gp,
            SUM(pgs.goals)                          AS goals,
            SUM(pgs.assists)                        AS assists,
            SUM(pgs.points)                         AS points,
            SUM(pgs.shots)                          AS shots,
            SUM(pgs.plus_minus)                     AS plus_minus_total
        FROM player_game_stats pgs
        JOIN players p ON p.player_id = pgs.player_id
        JOIN teams   t ON t.team_id   = pgs.team_id AND t.season_id = :sid
        JOIN games   g ON g.game_id   = pgs.game_id
        WHERE g.season_id   = :sid
          AND g.game_status = 'final'
          AND p.position   != 'G'
          AND t.team_code  != :excl
        GROUP BY pgs.player_id, p.first_name, p.last_name,
                 p.position, p.avg_toi_seconds, t.team_code, t.team_id
        HAVING COUNT(DISTINCT pgs.game_id) >= :min_gp
    """), {"sid": season_id, "excl": EXCLUDE_TEAM, "min_gp": MIN_GP}).mappings().all()
    return [dict(r) for r in rows]


def _fetch_standings(conn, season_id: int) -> dict[str, int]:
    """Returns {team_code: standings_position} — 1 = first place."""
    rows = conn.execute(text("""
        WITH pts AS (
            SELECT home_team_id AS team_id,
                   SUM(CASE WHEN home_score > away_score THEN 2
                            WHEN result_type IN ('OT','SO') THEN 0
                            ELSE 0 END) AS pts
            FROM games WHERE season_id = :sid AND game_status = 'final'
            GROUP BY home_team_id
            UNION ALL
            SELECT away_team_id,
                   SUM(CASE WHEN away_score > home_score THEN 2
                            WHEN result_type IN ('OT','SO') THEN 1
                            ELSE 0 END)
            FROM games WHERE season_id = :sid AND game_status = 'final'
            GROUP BY away_team_id
        )
        SELECT t.team_code, SUM(p.pts) AS total_pts
        FROM pts p
        JOIN teams t ON t.team_id = p.team_id AND t.season_id = :sid
        GROUP BY t.team_code
        ORDER BY total_pts DESC
    """), {"sid": season_id}).fetchall()

    return {r.team_code: (i + 1) for i, r in enumerate(rows)}


def _top_scorer_per_team(players: list[dict]) -> set[int]:
    """Returns set of player_ids who are their team's leading scorer."""
    by_team: dict[str, dict] = {}
    for p in players:
        tc = p["team_code"]
        if tc not in by_team or p["points"] > by_team[tc]["points"]:
            by_team[tc] = p
    return {p["player_id"] for p in by_team.values()}


# ── Metric derivation ─────────────────────────────────────────────────────────

def _derive_metrics(p: dict, standings: dict[str, int],
                    top_scorers: set[int]) -> dict:
    gp      = int(p["gp"]   or 0)
    pts     = int(p["points"] or 0)
    goals   = int(p["goals"]  or 0)
    shots   = int(p["shots"]  or 0)
    pm      = int(p["plus_minus_total"] or 0)
    toi_avg = int(p["avg_toi_seconds"]  or 0)   # seconds per game

    pts_pg   = pts  / gp if gp else 0
    shots_pg = shots / gp if gp else 0
    pm_pg    = pm   / gp if gp else 0
    sh_pct   = goals / shots if shots else 0

    # P/60: points per 60 minutes played (approximate using season-avg TOI)
    toi_hrs_per_game = toi_avg / 3600.0
    p60 = (pts_pg / toi_hrs_per_game) if toi_hrs_per_game > 0 else 0

    # Obscurity bonus
    is_top_scorer    = p["player_id"] in top_scorers
    team_pos         = standings.get(p["team_code"], 99)
    obscurity_bonus  = (0.0 if is_top_scorer else 1.0) + (0.0 if team_pos <= 2 else 0.5)

    return {
        **p,
        "pts_pg":        round(pts_pg,   3),
        "shots_pg":      round(shots_pg, 2),
        "pm_pg":         round(pm_pg,    3),
        "sh_pct":        round(sh_pct,   3),
        "p60":           round(p60,      3),
        "team_position": team_pos,
        "is_top_scorer": is_top_scorer,
        "obscurity_bonus": obscurity_bonus,
    }


def _z_scores(players: list[dict], key: str) -> dict[int, float]:
    vals = [p[key] for p in players if p[key] is not None]
    if len(vals) < 2:
        return {p["player_id"]: 0.0 for p in players}
    mu  = statistics.mean(vals)
    std = statistics.stdev(vals) or 1.0
    return {p["player_id"]: (p[key] - mu) / std for p in players}


# ── Reasoning generator ───────────────────────────────────────────────────────

def _build_reasoning(p: dict, rank: int, total_players: int,
                     p60_rank: int, shots_rank: int, pm_rank: int) -> str:
    lines = []

    # P/60 insight
    if p["p60"] > 0:
        lines.append(
            f"Produces {p['p60']:.2f} points per 60 minutes — "
            f"#{p60_rank} among all qualified non-MIN skaters."
        )

    # Points + context
    lines.append(
        f"{int(p['points'])} points in {int(p['gp'])} games "
        f"({p['pts_pg']:.2f} pts/game) for {p['team_code']}."
    )

    # Shooting efficiency or volume
    if p["sh_pct"] >= 0.15:
        lines.append(
            f"Shooting at {p['sh_pct']:.1%} — elite finishing efficiency "
            f"({int(p['goals'])}G on only {int(p['shots'])} shots)."
        )
    elif p["shots_pg"] >= 3.0:
        lines.append(
            f"Generating {p['shots_pg']:.1f} shots per game "
            f"(#{shots_rank} among non-MIN skaters) — a volume creator "
            f"who doesn't always get the points to show for it."
        )
    else:
        lines.append(
            f"{int(p['shots'])} shots on the season "
            f"({p['shots_pg']:.1f}/game)."
        )

    # Plus/minus
    if abs(p["pm_pg"]) >= 0.3:
        direction = "positive" if p["pm_pg"] > 0 else "negative"
        lines.append(
            f"Plus/minus of {p['pm_pg']:+.2f} per game — "
            f"{'two-way value that never gets mentioned' if direction == 'positive' else 'playing heavy minutes on a struggling team'}."
        )

    # Obscurity context
    if not p["is_top_scorer"]:
        lines.append(
            f"Not even {p['team_code']}'s leading scorer — completely off the radar."
        )
    if p["team_position"] > 4:
        lines.append(
            f"{p['team_code']} is sitting #{p['team_position']} in the standings, "
            f"so the whole team is underreported."
        )

    return " ".join(lines)


# ── Main entry point ──────────────────────────────────────────────────────────

def get_top_underrated(top_n: int = 3, season_id: int = SEASON_ID) -> list[dict]:
    """
    Returns the top `top_n` underrated players with scores, metrics, and reasoning.
    """
    engine = get_engine(pool_pre_ping=True)

    with engine.connect() as conn:
        raw       = _fetch_skater_stats(conn, season_id)
        standings = _fetch_standings(conn, season_id)

    top_scorers = _top_scorer_per_team(raw)
    players     = [_derive_metrics(p, standings, top_scorers) for p in raw]

    # Z-scores for each pillar
    z_p60    = _z_scores(players, "p60")
    z_shots  = _z_scores(players, "shots_pg")
    z_sh_pct = _z_scores(players, "sh_pct")
    z_pm     = _z_scores(players, "pm_pg")

    # Composite score
    for p in players:
        pid    = p["player_id"]
        score  = (
            z_p60.get(pid,    0) * 0.35 +
            z_shots.get(pid,  0) * 0.20 +
            z_sh_pct.get(pid, 0) * 0.20 +
            z_pm.get(pid,     0) * 0.15 +
            p["obscurity_bonus"] * 0.10
        )
        p["underrated_score"] = round(score, 4)

    players.sort(key=lambda x: x["underrated_score"], reverse=True)

    # Build per-pillar ranks for reasoning (ascending rank = better)
    def rank_by(key, reverse=True):
        ranked = sorted(players, key=lambda x: x[key], reverse=reverse)
        return {p["player_id"]: i + 1 for i, p in enumerate(ranked)}

    p60_ranks   = rank_by("p60")
    shots_ranks = rank_by("shots_pg")
    pm_ranks    = rank_by("pm_pg")

    total = len(players)
    result = []
    for rank, p in enumerate(players[:top_n], start=1):
        pid = p["player_id"]
        result.append({
            **p,
            "rank":      rank,
            "reasoning": _build_reasoning(
                p, rank, total,
                p60_ranks.get(pid, 0),
                shots_ranks.get(pid, 0),
                pm_ranks.get(pid, 0),
            ),
        })

    return result
