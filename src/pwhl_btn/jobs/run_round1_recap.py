"""
run_round1_recap.py — Round 1 playoff recap slides for TikTok.
  OTT vs BOS (last 4 games): 2 slides — hook + bullets
  MIN vs MTL (last 5 games): 2 slides — hook + bullets
Usage: python -m pwhl_btn.jobs.run_round1_recap
"""
from __future__ import annotations

from pathlib import Path
from sqlalchemy import text
from sqlalchemy.orm import Session

from pwhl_btn.db.db_config import get_engine
from pwhl_btn.db.db_queries import _logo_uri, _file_to_data_uri, PLAYERS_DIR
from pwhl_btn.render.round1_recap_render import render_hook, render_bullets, render_results_cover

SEASON_ID  = 9
OUTPUT_DIR = Path(__file__).resolve().parents[3] / "src" / "pwhl_btn" / "render" / "output"

engine = get_engine()


# ── Asset helpers ──────────────────────────────────────────────────────────────

def _player_photo(name: str) -> str | None:
    slug = name.lower().replace(" ", "_").replace("-", "_").replace("'", "")
    for ext in ("webp", "jpg", "jpeg", "png"):
        p = PLAYERS_DIR / f"{slug}.{ext}"
        if p.exists():
            return _file_to_data_uri(p)
    return None


# ── DB queries ─────────────────────────────────────────────────────────────────

def _h2h_games_last_n(session, team_a: str, team_b: str, last_n: int) -> list[dict]:
    """All H2H games ordered by date; returns only the final last_n (the playoff games)."""
    rows = session.execute(text("""
        SELECT g.game_id, g.date, g.home_score, g.away_score, g.result_type,
               ht.team_code AS home_code, at.team_code AS away_code,
               g.home_score_p1, g.home_score_p2, g.home_score_p3,
               g.away_score_p1, g.away_score_p2, g.away_score_p3
        FROM games g
        JOIN teams ht ON ht.team_id = g.home_team_id AND ht.season_id = :sid
        JOIN teams at ON at.team_id = g.away_team_id AND at.season_id = :sid
        WHERE g.season_id = :sid AND g.game_status = 'final'
          AND ((ht.team_code = :ta AND at.team_code = :tb)
            OR (ht.team_code = :tb AND at.team_code = :ta))
        ORDER BY g.date ASC
    """), {"sid": SEASON_ID, "ta": team_a, "tb": team_b}).fetchall()
    all_games = [dict(r._mapping) for r in rows]
    return all_games[-last_n:]


def _games_skaters(session, game_ids: list[int]) -> list[dict]:
    """Aggregate skater stats across a specific set of game_ids."""
    if not game_ids:
        return []
    ids = ",".join(str(i) for i in game_ids)
    rows = session.execute(text(f"""
        SELECT p.first_name, p.last_name, t.team_code,
               COUNT(DISTINCT pgs.game_id)            AS gp,
               SUM(pgs.goals)                         AS g,
               SUM(pgs.assists)                       AS a,
               SUM(pgs.goals + pgs.assists)           AS pts,
               SUM(pgs.shots)                         AS sog
        FROM player_game_stats pgs
        JOIN players p ON p.player_id = pgs.player_id
        JOIN teams   t ON t.team_id   = pgs.team_id AND t.season_id = :sid
        WHERE pgs.game_id IN ({ids})
        GROUP BY p.player_id, p.first_name, p.last_name, t.team_code
        ORDER BY pts DESC, g DESC, a DESC
    """), {"sid": SEASON_ID}).fetchall()
    return [dict(r._mapping) for r in rows]


def _games_goalies(session, game_ids: list[int]) -> list[dict]:
    """Aggregate goalie stats across a specific set of game_ids."""
    if not game_ids:
        return []
    ids = ",".join(str(i) for i in game_ids)
    rows = session.execute(text(f"""
        SELECT p.first_name, p.last_name, t.team_code,
               COUNT(DISTINCT ggs.game_id)                                          AS gp,
               SUM(ggs.saves)                                                       AS sv,
               SUM(ggs.shots_against)                                               AS sa,
               SUM(ggs.goals_against)                                               AS ga,
               ROUND(SUM(ggs.saves) / NULLIF(SUM(ggs.shots_against), 0), 3)        AS sv_pct,
               SUM(CASE WHEN ggs.decision = 'W' THEN 1 ELSE 0 END)                 AS wins
        FROM goalie_game_stats ggs
        JOIN players p ON p.player_id = ggs.player_id
        JOIN teams   t ON t.team_id   = ggs.team_id AND t.season_id = :sid
        WHERE ggs.game_id IN ({ids})
        GROUP BY p.player_id, p.first_name, p.last_name, t.team_code
        ORDER BY sv_pct DESC
    """), {"sid": SEASON_ID}).fetchall()
    return [dict(r._mapping) for r in rows]


# ── Stat helpers ───────────────────────────────────────────────────────────────

def _wins(games: list[dict], team: str) -> int:
    return sum(1 for g in games
               if (g["home_code"] == team and g["home_score"] > g["away_score"])
               or (g["away_code"] == team and g["away_score"] > g["home_score"]))


def _gf_ga(games: list[dict], team: str) -> tuple[int, int]:
    gf = sum(g["home_score"] if g["home_code"] == team else g["away_score"] for g in games)
    ga = sum(g["away_score"] if g["home_code"] == team else g["home_score"] for g in games)
    return gf, ga


def _period_totals(games: list[dict], team: str) -> list[dict]:
    out = []
    for label, hk, ak in [("1st", "home_score_p1", "away_score_p1"),
                           ("2nd", "home_score_p2", "away_score_p2"),
                           ("3rd", "home_score_p3", "away_score_p3")]:
        gf = sum((g[hk] or 0) if g["home_code"] == team else (g[ak] or 0) for g in games)
        ga = sum((g[ak] or 0) if g["home_code"] == team else (g[hk] or 0) for g in games)
        out.append({"label": label, "gf": gf, "ga": ga, "gd": gf - ga})
    return out


def _fmt_svp(val) -> str:
    if val is None:
        return ".---"
    f = float(val)
    return f".{round(f * 1000):03d}"


def _determine_winner(games: list[dict], team_a: str, team_b: str) -> tuple[str, str]:
    wins_a = _wins(games, team_a)
    return (team_a, team_b) if wins_a > (len(games) - wins_a) else (team_b, team_a)


# ── Hardcoded bullets ──────────────────────────────────────────────────────────

OTT_BOS_BULLETS = [
    {
        "number": "01",
        "stat":   "10-7",
        "label":  "GOALS FOR vs AGAINST",
        "detail": "OTT outscored BOS across all 4 playoff games",
    },
    {
        "number": "02",
        "stat":   "5 PTS",
        "label":  "FANUZA KADIROVA · OTT",
        "detail": "Led Ottawa in scoring — 2G + 3A in the series",
    },
    {
        "number": "03",
        "stat":   ".943",
        "label":  "GWYNETH PHILIPS · SV%",
        "detail": "#1 goalie in the playoffs — held BOS to just 7 goals in 4 starts",
    },
    {
        "number": "04",
        "stat":   "4-0",
        "label":  "1ST PERIOD GOALS",
        "detail": "OTT dominated the opening period, outscoring BOS 4-0 across the series",
    },
]

MTL_MIN_BULLETS = [
    {
        "number": "01",
        "stat":   "10-10",
        "label":  "GOALS FOR vs AGAINST",
        "detail": "A perfectly even series — decided in 5 games",
    },
    {
        "number": "02",
        "stat":   "5 PTS",
        "label":  "MARIE-PHILIP POULIN · MTL",
        "detail": "Led Montréal in scoring — including the series-clinching game winner",
    },
    {
        "number": "03",
        "stat":   "HAT TRICK",
        "label":  "LAURA STACEY · MTL",
        "detail": "First PWHL playoff hat trick — 3 goals for Stacey in Game 1",
    },
    {
        "number": "04",
        "stat":   ".942",
        "label":  "ANN-RENÉE DESBIENS · SV%",
        "detail": "2nd-best SV% of the playoffs — 59 saves across 5 starts",
    },
    {
        "number": "05",
        "stat":   ".916",
        "label":  "MADDIE ROONEY · MIN SV%",
        "detail": "Kept Minnesota in multiple games throughout the series",
    },
]


# ── Main ───────────────────────────────────────────────────────────────────────

def run(out_dir: Path | None = None) -> None:
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    logos = {
        "OTT": _logo_uri("OTT"),
        "BOS": _logo_uri("BOS"),
        "MIN": _logo_uri("MIN"),
        "MTL": _logo_uri("MTL"),
    }

    with Session(engine) as session:
        games_ob = _h2h_games_last_n(session, "OTT", "BOS", 4)
        games_mm = _h2h_games_last_n(session, "MIN", "MTL", 5)

    # ── Overall results cover ───────────────────────────────────────────────────
    print("\n=== Overall Results Cover ===")
    winner_mm, loser_mm_c = _determine_winner(games_mm, "MIN", "MTL")
    wins_mm_c = _wins(games_mm, winner_mm)
    winner_ob_c, loser_ob_c = _determine_winner(games_ob, "OTT", "BOS")
    wins_ob_c = _wins(games_ob, winner_ob_c)

    FULL_NAMES = {"MTL": "Montréal Victoire", "MIN": "Minnesota Frost",
                  "OTT": "Ottawa Charge",     "BOS": "Boston Fleet"}

    cover_ctx = {
        "r1a": {
            "winner_logo":   logos[winner_mm],
            "winner_code":   winner_mm,
            "winner_name":   FULL_NAMES[winner_mm],
            "winner_series": f"{wins_mm_c}-{len(games_mm) - wins_mm_c}",
            "loser_logo":    logos[loser_mm_c],
            "loser_code":    loser_mm_c,
            "loser_name":    FULL_NAMES[loser_mm_c],
            "loser_series":  f"{len(games_mm) - wins_mm_c}-{wins_mm_c}",
        },
        "r1b": {
            "winner_logo":   logos[winner_ob_c],
            "winner_code":   winner_ob_c,
            "winner_name":   FULL_NAMES[winner_ob_c],
            "winner_series": f"{wins_ob_c}-{len(games_ob) - wins_ob_c}",
            "loser_logo":    logos[loser_ob_c],
            "loser_code":    loser_ob_c,
            "loser_name":    FULL_NAMES[loser_ob_c],
            "loser_series":  f"{len(games_ob) - wins_ob_c}-{wins_ob_c}",
        },
        # Finals: MTL vs OTT — no predicted winner, show alphabetically
        "fin_a_logo": logos[winner_mm],
        "fin_a_code": winner_mm,
        "fin_a_name": FULL_NAMES[winner_mm],
        "fin_b_logo": logos[winner_ob_c],
        "fin_b_code": winner_ob_c,
        "fin_b_name": FULL_NAMES[winner_ob_c],
    }
    render_results_cover(cover_ctx, slug="recap_00_results_cover", out_dir=out_dir)

    # ── OTT vs BOS ─────────────────────────────────────────────────────────────
    print("\n=== OTT vs BOS · Round 1 Recap ===")
    winner_ob, loser_ob = _determine_winner(games_ob, "OTT", "BOS")
    wins_ob = _wins(games_ob, winner_ob)

    hook_ob = {
        "badge_label":  "PWHL PLAYOFFS 2025–26",
        "player_photo": _player_photo("gwyneth philips") if winner_ob == "OTT" else _player_photo("hilary knight"),
        "logo_winner":  logos[winner_ob],
        "logo_loser":   logos[loser_ob],
        "winner_code":  winner_ob,
        "loser_code":   loser_ob,
        "result":       f"{wins_ob}–{len(games_ob) - wins_ob}",
    }
    bullets_ob = {
        "badge_label": "ROUND 1 RECAP",
        "winner_code": winner_ob,
        "loser_code":  loser_ob,
        "logo_winner": logos[winner_ob],
        "logo_loser":  logos[loser_ob],
        "result":      f"{wins_ob}–{len(games_ob) - wins_ob}",
        "n_games":     len(games_ob),
        "bullets":     OTT_BOS_BULLETS,
    }

    print("  Slide 1/2 — hook")
    render_hook(hook_ob, slug="recap_ob_01_hook", out_dir=out_dir)
    print("  Slide 2/2 — bullets")
    render_bullets(bullets_ob, slug="recap_ob_02_bullets", out_dir=out_dir)

    # ── MIN vs MTL ─────────────────────────────────────────────────────────────
    print("\n=== MIN vs MTL · Round 1 Recap ===")
    winner_mm, loser_mm = _determine_winner(games_mm, "MIN", "MTL")
    wins_mm = _wins(games_mm, winner_mm)

    hook_mm = {
        "badge_label":  "PWHL PLAYOFFS 2025–26",
        "player_photo": _player_photo("marie philip poulin") if winner_mm == "MTL" else _player_photo("taylor heise"),
        "logo_winner":  logos[winner_mm],
        "logo_loser":   logos[loser_mm],
        "winner_code":  winner_mm,
        "loser_code":   loser_mm,
        "result":       f"{wins_mm}–{len(games_mm) - wins_mm}",
    }
    bullets_mm = {
        "badge_label": "ROUND 1 RECAP",
        "winner_code": winner_mm,
        "loser_code":  loser_mm,
        "logo_winner": logos[winner_mm],
        "logo_loser":  logos[loser_mm],
        "result":      f"{wins_mm}–{len(games_mm) - wins_mm}",
        "n_games":     len(games_mm),
        "bullets":     MTL_MIN_BULLETS,
    }

    print("  Slide 1/2 — hook")
    render_hook(hook_mm, slug="recap_mm_01_hook", out_dir=out_dir)
    print("  Slide 2/2 — bullets")
    render_bullets(bullets_mm, slug="recap_mm_02_bullets", out_dir=out_dir)

    print(f"\nDone — 4 slides written to {out_dir}")
    print("  recap_ob_01_hook.png   · recap_ob_02_bullets.png  (OTT vs BOS)")
    print("  recap_mm_01_hook.png   · recap_mm_02_bullets.png  (MIN vs MTL)")


if __name__ == "__main__":
    run()
