"""
run_prediction_slides.py — Fits model, runs Bayesian simulation, renders 4 slides.
Usage: python -m pwhl_btn.jobs.run_prediction_slides
       python -m pwhl_btn.jobs.run_prediction_slides --prior 5
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.orm import Session

from pwhl_btn.db.db_config import get_engine
from pwhl_btn.db.db_queries import _logo_uri
from pwhl_btn.analytics.poisson_model import DixonColesModel
from pwhl_btn.analytics.bayes_update import BayesianMatchupPredictor
from pwhl_btn.render.prediction_render import (
    render_pred_cover, render_pred_matchup, render_pred_bayes_shift,
    render_pred_methodology,
)

SEASON_ID        = 8
BEST_OF_5        = ["A", "A", "B", "B", "A"]
PRIOR_STRENGTH   = 10.0
N_SIMS           = 50_000
SEED             = 42
OUTPUT_DIR       = Path(__file__).resolve().parents[3] / "src" / "pwhl_btn" / "render" / "output"

engine = get_engine()

TEAM_NAMES = {
    "MTL": "Montréal", "MIN": "Minnesota",
    "OTT": "Ottawa",   "BOS": "Boston",
}

SEEDS = {
    "MTL": "1st Seed", "OTT": "2nd Seed",
    "BOS": "3rd Seed", "MIN": "4th Seed",
}


def _r1_cover_pair(team_a: str, team_b: str, p_a: float, p_b: float, logos: dict) -> dict:
    """Return winner/loser info for one R1 matchup, sorted by model probability."""
    if p_a >= p_b:
        w, l, wp, lp = team_a, team_b, p_a, p_b
    else:
        w, l, wp, lp = team_b, team_a, p_b, p_a
    return {
        "winner_code": w, "winner_logo": logos[w],
        "winner_name": TEAM_NAMES[w], "winner_seed": SEEDS[w],
        "winner_pct":  round(wp * 100, 1),
        "loser_code":  l, "loser_logo":  logos[l],
        "loser_name":  TEAM_NAMES[l],  "loser_seed":  SEEDS[l],
        "loser_pct":   round(lp * 100, 1),
    }


def _load_all_games():
    with Session(engine) as s:
        rows = s.execute(text("""
            SELECT ht.team_code AS home_code, at.team_code AS away_code,
                   g.home_score, g.away_score, g.result_type, g.date
            FROM games g
            JOIN teams ht ON ht.team_id = g.home_team_id AND ht.season_id = :sid
            JOIN teams at ON at.team_id = g.away_team_id AND at.season_id = :sid
            WHERE g.season_id = :sid AND g.game_status = 'final'
            ORDER BY g.date ASC
        """), {"sid": SEASON_ID}).fetchall()
    return [dict(r._mapping) for r in rows]


def _load_h2h(ta, tb):
    with Session(engine) as s:
        rows = s.execute(text("""
            SELECT ht.team_code AS home_code, at.team_code AS away_code,
                   g.home_score, g.away_score, g.result_type
            FROM games g
            JOIN teams ht ON ht.team_id = g.home_team_id AND ht.season_id = :sid
            JOIN teams at ON at.team_id = g.away_team_id AND at.season_id = :sid
            WHERE g.season_id = :sid AND g.game_status = 'final'
              AND ((ht.team_code=:ta AND at.team_code=:tb)
                OR (ht.team_code=:tb AND at.team_code=:ta))
            ORDER BY g.date ASC
        """), {"sid": SEASON_ID, "ta": ta, "tb": tb}).fetchall()
    return [dict(r._mapping) for r in rows]


def _length_bars(dist: dict) -> tuple[list[dict], float]:
    max_pct = max(dist.values()) * 100
    bars = []
    for games, frac in dist.items():
        pct = round(frac * 100, 1)
        bars.append({
            "games": games,
            "pct":   pct,
            "bar_h": round(pct / max_pct * 100, 1),
        })
    return bars, max_pct


def _matchup_ctx(team_a, team_b, mle_result, bayes_result, logo_a, logo_b):
    dist   = bayes_result.length_dist
    bars, max_pct = _length_bars(dist)
    favored = team_a if bayes_result.p_a_wins >= 0.5 else team_b

    lam_ah  = round(bayes_result.post_a_home[0] / bayes_result.post_a_home[1], 2)
    lam_ba  = round(bayes_result.post_b_at_a[0] / bayes_result.post_b_at_a[1], 2)
    lam_bh  = round(bayes_result.post_b_home[0] / bayes_result.post_b_home[1], 2)
    lam_ab  = round(bayes_result.post_a_at_b[0] / bayes_result.post_a_at_b[1], 2)

    return {
        "team_a":        team_a,
        "team_b":        team_b,
        "name_a":        TEAM_NAMES[team_a],
        "name_b":        TEAM_NAMES[team_b],
        "logo_a":        logo_a,
        "logo_b":        logo_b,
        "favored":       favored,
        "p_a_pct":       round(bayes_result.p_a_wins * 100, 1),
        "p_b_pct":       round(bayes_result.p_b_wins * 100, 1),
        "ci_low":        round(bayes_result.ci_low * 100, 1),
        "ci_high":       round(bayes_result.ci_high * 100, 1),
        "lengths":       bars,
        "max_pct":       max_pct,
        "lam_a_home":    f"{lam_ah:.2f}",
        "lam_b_at_a":    f"{lam_ba:.2f}",
        "lam_b_home":    f"{lam_bh:.2f}",
        "lam_a_at_b":    f"{lam_ab:.2f}",
        "lam_b_home_val": lam_bh,
        "lam_a_at_b_val": lam_ab,
    }


def run(prior_strength: float = PRIOR_STRENGTH):
    rng = random.Random(SEED)

    print("Loading game data...")
    all_games = _load_all_games()

    print("Fitting Dixon-Coles model...")
    model = DixonColesModel()
    model.fit(all_games)

    bayes = BayesianMatchupPredictor(model, prior_strength=prior_strength)

    logos = {t: _logo_uri(t) for t in ("MTL", "MIN", "OTT", "BOS")}

    # ── Simulate both matchups ────────────────────────────────────────────────
    print("Simulating MTL vs MIN...")
    h2h_mm  = _load_h2h("MTL", "MIN")
    mle_mm  = model.simulate_series("MTL", "MIN", BEST_OF_5, N_SIMS, random.Random(SEED))
    bayes_mm = bayes.simulate_series("MTL", "MIN", h2h_mm, BEST_OF_5, N_SIMS, rng)

    print("Simulating OTT vs BOS...")
    h2h_ob  = _load_h2h("OTT", "BOS")
    mle_ob  = model.simulate_series("OTT", "BOS", BEST_OF_5, N_SIMS, random.Random(SEED))
    bayes_ob = bayes.simulate_series("OTT", "BOS", h2h_ob, BEST_OF_5, N_SIMS, rng)

    # ── Build contexts ────────────────────────────────────────────────────────
    ctx_mm = _matchup_ctx("MTL", "MIN", mle_mm, bayes_mm, logos["MTL"], logos["MIN"])
    ctx_ob = _matchup_ctx("OTT", "BOS", mle_ob, bayes_ob, logos["OTT"], logos["BOS"])

    # Lambda rows for the shift slide (OTT vs BOS is the interesting case)
    lambda_rows = [
        {"config": "OTT home", "team": "OTT", "is_ott": True,
         "mle":  f"{bayes_ob.mle_lam_a_home:.2f}",
         "post": f"{bayes_ob.post_a_home[0]/bayes_ob.post_a_home[1]:.2f}"},
        {"config": "OTT home", "team": "BOS",  "is_ott": False,
         "mle":  f"{bayes_ob.mle_lam_b_at_a:.2f}",
         "post": f"{bayes_ob.post_b_at_a[0]/bayes_ob.post_b_at_a[1]:.2f}"},
        {"config": "BOS home", "team": "BOS",  "is_ott": False,
         "mle":  f"{bayes_ob.mle_lam_b_home:.2f}",
         "post": f"{bayes_ob.post_b_home[0]/bayes_ob.post_b_home[1]:.2f}"},
        {"config": "BOS home", "team": "OTT", "is_ott": True,
         "mle":  f"{bayes_ob.mle_lam_a_at_b:.2f}",
         "post": f"{bayes_ob.post_a_at_b[0]/bayes_ob.post_a_at_b[1]:.2f}"},
    ]

    shift_ctx = {
        "mtl_logo":   logos["MTL"],
        "min_logo":   logos["MIN"],
        "ott_logo":   logos["OTT"],
        "bos_logo":   logos["BOS"],
        "mtl_mle":    round(mle_mm.p_a_wins  * 100, 1),
        "min_mle":    round(mle_mm.p_b_wins  * 100, 1),
        "mtl_bayes":  round(bayes_mm.p_a_wins * 100, 1),
        "min_bayes":  round(bayes_mm.p_b_wins * 100, 1),
        "mtl_shift":  round((bayes_mm.p_a_wins - mle_mm.p_a_wins) * 100, 1),
        "ott_mle":    round(mle_ob.p_a_wins  * 100, 1),
        "bos_mle":    round(mle_ob.p_b_wins  * 100, 1),
        "ott_bayes":  round(bayes_ob.p_a_wins * 100, 1),
        "bos_bayes":  round(bayes_ob.p_b_wins * 100, 1),
        "ott_shift":  round((bayes_ob.p_a_wins - mle_ob.p_a_wins) * 100, 1),
        "lambda_rows": lambda_rows,
    }

    # ── Build cover bracket data ──────────────────────────────────────────────
    r1a = _r1_cover_pair("MTL", "MIN", bayes_mm.p_a_wins, bayes_mm.p_b_wins, logos)
    r1b = _r1_cover_pair("OTT", "BOS", bayes_ob.p_a_wins, bayes_ob.p_b_wins, logos)

    # Finals simulation: R1a winner (MTL, home ice) vs R1b winner
    fin_a = r1a["winner_code"]
    fin_b = r1b["winner_code"]
    print(f"Simulating finals: {fin_a} vs {fin_b}...")
    h2h_fin  = _load_h2h(fin_a, fin_b)
    bayes_fin = bayes.simulate_series(fin_a, fin_b, h2h_fin, BEST_OF_5, N_SIMS, rng)

    # ── Render ────────────────────────────────────────────────────────────────
    print("\nRendering slide 1/4 — cover")
    render_pred_cover({
        "r1a": r1a,
        "r1b": r1b,
        "fin_winner_logo": logos["MTL"],
        "fin_winner_code": "MTL",
        "fin_winner_name": TEAM_NAMES["MTL"],
        "fin_winner_pct":  round(bayes_fin.p_a_wins * 100, 1),
        "fin_loser_logo":  logos[fin_b],
        "fin_loser_code":  fin_b,
        "fin_loser_name":  TEAM_NAMES[fin_b],
        "fin_loser_pct":   round(bayes_fin.p_b_wins * 100, 1),
        "champ_logo": logos["MTL"],
        "champ_code": "MTL",
        "champ_name": TEAM_NAMES["MTL"],
    }, OUTPUT_DIR)

    print("Rendering slide 2/4 — MTL vs MIN")
    render_pred_matchup(ctx_mm, "02_mtl_min", OUTPUT_DIR)

    print("Rendering slide 3/4 — OTT vs BOS")
    render_pred_matchup(ctx_ob, "03_ott_bos", OUTPUT_DIR)

    print("Rendering slide 4/5 — Bayesian shift")
    render_pred_bayes_shift(shift_ctx, OUTPUT_DIR)

    print("Rendering slide 5/5 — Methodology")
    render_pred_methodology({
        "n_reg_games": len(all_games),
        "n_sims_fmt":  f"{N_SIMS:,}",
        "ex_matchup":  "MTL vs MIN",
        "ex_h2h_games": len(h2h_mm),
        "ex_team":     "MTL",
        "ex_mle_pct":  round(mle_mm.p_a_wins * 100, 1),
        "ex_bayes_pct": round(bayes_mm.p_a_wins * 100, 1),
        "ex_shift":    round((bayes_mm.p_a_wins - mle_mm.p_a_wins) * 100, 1),
    }, OUTPUT_DIR)

    print(f"\nDone. 5 slides written to {OUTPUT_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prior", type=float, default=PRIOR_STRENGTH,
                        help="Prior strength (equiv. H2H games; default %(default)s)")
    args = parser.parse_args()
    run(prior_strength=args.prior)
