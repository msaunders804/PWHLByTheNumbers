"""
run_final_prediction.py — Walter Cup Final prediction: MTL vs OTT.

Four-stage model:
  Stage 1 — Dixon-Coles MLE on all 120 Season 8 (2025-26 regular season) games.
             Establishes baseline attack/defense parameters for all 8 teams.

  Stage 2 — Season 9 playoff form adjustment.
             For each team, compare actual playoff goals scored/allowed against
             what the S8 model expected.  Compute attack and defense factors and
             blend them into the prior lambdas (form_weight controls the blend).

  Stage 3 — Bayesian Gamma-Poisson update using the 4 Season 8 MTL vs OTT H2H
             games.  Form-adjusted lambdas are the prior; H2H goals are the
             observations.

  Stage 4 — Simulate 50K best-of-5 series sampling from posteriors.

Note on DB layout:
  Season 8 team records in `teams` only have expansion teams (NY/SEA/TOR/VAN).
  MTL/OTT/BOS/MIN have team_ids resolved from Season 9, which are consistent
  across seasons (team_ids are league-wide, not season-scoped).

MTL holds home ice (1st seed). Best-of-5: AABBA.

Usage:
  python -m pwhl_btn.jobs.run_final_prediction
  python -m pwhl_btn.jobs.run_final_prediction --sims 100000
  python -m pwhl_btn.jobs.run_final_prediction --form-weight 0.7 --prior 4
"""
from __future__ import annotations

import argparse
import random
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import text
from sqlalchemy.orm import Session

from pwhl_btn.db.db_config import get_engine
from pwhl_btn.db.db_queries import _logo_uri
from pwhl_btn.analytics.poisson_model import DixonColesModel
from pwhl_btn.analytics.bayes_update import (
    _gamma_posterior,
    _sample_gamma,
    _poisson_sample,
)
from pwhl_btn.render.prediction_render import render_pred_matchup

SEASON_8 = 8
SEASON_9 = 9

TEAM_A = "MTL"   # higher seed — home ice
TEAM_B = "OTT"

BEST_OF_5 = ["A", "A", "B", "B", "A"]   # A = MTL home

FULL_NAMES = {
    "MTL": "Montréal Victoire",
    "OTT": "Ottawa Charge",
}

OUTPUT_DIR = Path(__file__).resolve().parents[3] / "src" / "pwhl_btn" / "render" / "output"

engine = get_engine(pool_pre_ping=True)


# ── Team code resolution ───────────────────────────────────────────────────────

def _build_team_code_map(session) -> dict[int, str]:
    rows = session.execute(text(
        "SELECT team_id, team_code, season_id FROM teams ORDER BY season_id DESC"
    )).fetchall()
    code_map: dict[int, str] = {}
    for r in rows:
        if r.team_id not in code_map:
            code_map[r.team_id] = r.team_code
    return code_map


# ── Data loaders ───────────────────────────────────────────────────────────────

def _load_s8_games() -> list[dict]:
    with Session(engine) as session:
        code_map = _build_team_code_map(session)
        rows = session.execute(text("""
            SELECT game_id, date, home_team_id, away_team_id,
                   home_score, away_score, result_type
            FROM games
            WHERE season_id = :sid AND game_status = 'final'
            ORDER BY date ASC
        """), {"sid": SEASON_8}).fetchall()

    return [
        {
            "game_id":     r.game_id,
            "date":        r.date,
            "home_code":   code_map[r.home_team_id],
            "away_code":   code_map[r.away_team_id],
            "home_score":  r.home_score,
            "away_score":  r.away_score,
            "result_type": r.result_type,
        }
        for r in rows
        if code_map.get(r.home_team_id) and code_map.get(r.away_team_id)
    ]


def _load_s8_h2h(team_a: str, team_b: str) -> list[dict]:
    with Session(engine) as session:
        code_map = _build_team_code_map(session)
        rev_map  = {v: k for k, v in code_map.items()}
        id_a, id_b = rev_map.get(team_a), rev_map.get(team_b)
        if not id_a or not id_b:
            return []
        rows = session.execute(text("""
            SELECT game_id, date, home_team_id, away_team_id,
                   home_score, away_score, result_type
            FROM games
            WHERE season_id = :sid AND game_status = 'final'
              AND ((home_team_id = :ia AND away_team_id = :ib)
                OR (home_team_id = :ib AND away_team_id = :ia))
            ORDER BY date ASC
        """), {"sid": SEASON_8, "ia": id_a, "ib": id_b}).fetchall()

    return [
        {
            "game_id":     r.game_id,
            "date":        r.date,
            "home_code":   code_map[r.home_team_id],
            "away_code":   code_map[r.away_team_id],
            "home_score":  r.home_score,
            "away_score":  r.away_score,
            "result_type": r.result_type,
        }
        for r in rows
    ]


def _load_s9_games() -> list[dict]:
    with Session(engine) as session:
        rows = session.execute(text("""
            SELECT ht.team_code AS home_code, at.team_code AS away_code,
                   g.home_score, g.away_score, g.result_type, g.date
            FROM games g
            JOIN teams ht ON ht.team_id = g.home_team_id AND ht.season_id = :sid
            JOIN teams at ON at.team_id = g.away_team_id AND at.season_id = :sid
            WHERE g.season_id = :sid AND g.game_status = 'final'
            ORDER BY g.date ASC
        """), {"sid": SEASON_9}).fetchall()
    return [dict(r._mapping) for r in rows]


# ── Form factor computation ────────────────────────────────────────────────────

def compute_form_factors(
    model: DixonColesModel,
    s9_games: list[dict],
    team: str,
) -> tuple[float, float]:
    """
    Compare actual playoff goals scored/allowed vs model expectation.

    attack_factor  = obs_scored  / exp_scored   (>1 = better than model expected)
    defense_factor = exp_allowed / obs_allowed  (>1 = tighter defense than expected)

    Returns (attack_factor, defense_factor).
    """
    team_games = [g for g in s9_games
                  if g["home_code"] == team or g["away_code"] == team]

    obs_scored = obs_allowed = exp_scored = exp_allowed = 0.0

    for g in team_games:
        is_home = g["home_code"] == team
        opp     = g["away_code"] if is_home else g["home_code"]

        if opp not in model.attack:
            continue

        if is_home:
            lam_team, lam_opp = model.lambdas(team, opp)
            scored  = g["home_score"]
            allowed = g["away_score"]
        else:
            lam_opp, lam_team = model.lambdas(opp, team)
            scored  = g["away_score"]
            allowed = g["home_score"]

        obs_scored  += scored
        obs_allowed += allowed
        exp_scored  += lam_team
        exp_allowed += lam_opp

    if exp_scored == 0 or obs_allowed == 0:
        return 1.0, 1.0

    return obs_scored / exp_scored, exp_allowed / obs_allowed


def blend(base_lam: float, factor: float, form_weight: float) -> float:
    """base_lam * ((1-w) + w*factor) — shifts lambda toward form-adjusted value."""
    return base_lam * (1.0 - form_weight + form_weight * factor)


# ── Series simulation ──────────────────────────────────────────────────────────

def simulate_series(
    post_ah: tuple, post_ba: tuple,
    post_bh: tuple, post_ab: tuple,
    n_sims: int, rng: random.Random, ci_chunks: int = 100,
) -> dict:
    wins_to_win = 3
    chunk_size  = max(1, n_sims // ci_chunks)

    a_series_wins  = 0
    series_lengths = []
    chunk_rates:   list[float] = []
    chunk_wins     = 0
    chunk_count    = 0

    for _ in range(n_sims):
        lam_ah = _sample_gamma(*post_ah, rng)
        lam_ba = _sample_gamma(*post_ba, rng)
        lam_bh = _sample_gamma(*post_bh, rng)
        lam_ab = _sample_gamma(*post_ab, rng)

        wins_a = wins_b = 0
        for g_idx in range(len(BEST_OF_5)):
            if wins_a == wins_to_win or wins_b == wins_to_win:
                break
            is_a_home = BEST_OF_5[g_idx] == "A"
            lh, la = (lam_ah, lam_ba) if is_a_home else (lam_bh, lam_ab)
            hg = _poisson_sample(lh, rng)
            ag = _poisson_sample(la, rng)
            if hg == ag:
                home_wins = rng.random() < lh / (lh + la)
            else:
                home_wins = hg > ag
            a_wins_game = home_wins if is_a_home else not home_wins
            if a_wins_game:
                wins_a += 1
            else:
                wins_b += 1

        if wins_a == wins_to_win:
            a_series_wins += 1
            chunk_wins    += 1
        series_lengths.append(wins_a + wins_b)
        chunk_count += 1
        if chunk_count == chunk_size:
            chunk_rates.append(chunk_wins / chunk_size)
            chunk_wins  = 0
            chunk_count = 0

    sorted_rates = sorted(chunk_rates)
    n_ch     = len(sorted_rates)
    len_dist = Counter(series_lengths)
    total    = sum(len_dist.values())

    return {
        "p_a":         a_series_wins / n_sims,
        "ci_low":      sorted_rates[max(0, int(n_ch * 0.05))],
        "ci_high":     sorted_rates[min(n_ch - 1, int(n_ch * 0.95))],
        "length_dist": {k: len_dist[k] / total for k in sorted(len_dist)},
    }


# ── Main ───────────────────────────────────────────────────────────────────────

def run(
    n_sims: int        = 50_000,
    form_weight: float = 0.70,
    prior_strength: float = 4.0,
    seed: int | None   = None,
):
    rng = random.Random(seed)

    print(f"\nWalter Cup Final Prediction: {TEAM_A} vs {TEAM_B}")
    print("=" * 62)

    # ── Stage 1: Fit MLE on Season 8 ──────────────────────────────────────────
    print(f"\n[1/4] Loading Season 8 regular season games...")
    s8_games = _load_s8_games()
    print(f"  {len(s8_games)} games  |  teams: "
          f"{sorted({g['home_code'] for g in s8_games} | {g['away_code'] for g in s8_games})}")

    print(f"\n[2/4] Fitting Dixon-Coles MLE (Season 8)...")
    model = DixonColesModel()
    model.fit(s8_games)
    print(model.summary())

    mle_lam_ah, mle_lam_ba = model.lambdas(TEAM_A, TEAM_B)
    mle_lam_bh, mle_lam_ab = model.lambdas(TEAM_B, TEAM_A)

    print(f"\n  MLE lambdas (before form adjustment):")
    print(f"    {TEAM_A} home: {TEAM_A} {mle_lam_ah:.3f}  {TEAM_B} {mle_lam_ba:.3f}")
    print(f"    {TEAM_B} home: {TEAM_B} {mle_lam_bh:.3f}  {TEAM_A} {mle_lam_ab:.3f}")

    # ── Stage 2: Season 9 form adjustment ─────────────────────────────────────
    print(f"\n[3/4] Season 9 playoff form adjustment (weight={form_weight:.0%})...")
    s9_games = _load_s9_games()

    mtl_atk, mtl_def = compute_form_factors(model, s9_games, TEAM_A)
    ott_atk, ott_def = compute_form_factors(model, s9_games, TEAM_B)

    print(f"\n  {TEAM_A} playoff form vs model expectation:")
    print(f"    Attack factor : {mtl_atk:.3f}  "
          f"({'scored more' if mtl_atk > 1 else 'scored less'} than expected)")
    print(f"    Defense factor: {mtl_def:.3f}  "
          f"({'tighter' if mtl_def > 1 else 'leakier'} defense than expected)")

    print(f"\n  {TEAM_B} playoff form vs model expectation:")
    print(f"    Attack factor : {ott_atk:.3f}  "
          f"({'scored more' if ott_atk > 1 else 'scored less'} than expected)")
    print(f"    Defense factor: {ott_def:.3f}  "
          f"({'tighter' if ott_def > 1 else 'leakier'} defense than expected)")

    # Apply: for each lambda, the combined factor is the scorer's attack × opponent's defense
    # MTL scoring at home: MTL attack × OTT defense (did OTT tighten up? matters here)
    # OTT scoring at MTL home: OTT attack × MTL defense
    adj_lam_ah = blend(mle_lam_ah, mtl_atk * ott_def, form_weight)
    adj_lam_ba = blend(mle_lam_ba, ott_atk * mtl_def, form_weight)
    adj_lam_bh = blend(mle_lam_bh, ott_atk * mtl_def, form_weight)
    adj_lam_ab = blend(mle_lam_ab, mtl_atk * ott_def, form_weight)

    print(f"\n  Form-adjusted lambdas (form_weight={form_weight:.0%}):")
    print(f"    {TEAM_A} home: {TEAM_A} {mle_lam_ah:.3f} -> {adj_lam_ah:.3f}  "
          f"{TEAM_B} {mle_lam_ba:.3f} -> {adj_lam_ba:.3f}")
    print(f"    {TEAM_B} home: {TEAM_B} {mle_lam_bh:.3f} -> {adj_lam_bh:.3f}  "
          f"{TEAM_A} {mle_lam_ab:.3f} -> {adj_lam_ab:.3f}")

    # ── Season 8 H2H Bayesian update ──────────────────────────────────────────
    print(f"\n  Season 8 H2H update (prior_strength={prior_strength:.0f})...")
    h2h = _load_s8_h2h(TEAM_A, TEAM_B)

    for g in h2h:
        winner = g["home_code"] if g["home_score"] > g["away_score"] else g["away_code"]
        print(f"    {g['date']}  {g['home_code']} {g['home_score']}-{g['away_score']} "
              f"{g['away_code']}  ({g['result_type']})  W:{winner}")

    a_home = [g for g in h2h if g["home_code"] == TEAM_A]
    b_home = [g for g in h2h if g["home_code"] == TEAM_B]
    a_wins  = sum(
        1 for g in h2h
        if (g["home_code"] == TEAM_A and g["home_score"] > g["away_score"])
        or (g["away_code"] == TEAM_A and g["away_score"] > g["home_score"])
    )
    print(f"    H2H: {TEAM_A} {a_wins}-{len(h2h)-a_wins}  "
          f"({len(a_home)} at {TEAM_A} home / {len(b_home)} at {TEAM_B} home)")

    post_ah = _gamma_posterior(adj_lam_ah, [g["home_score"] for g in a_home], prior_strength)
    post_ba = _gamma_posterior(adj_lam_ba, [g["away_score"] for g in a_home], prior_strength)
    post_bh = _gamma_posterior(adj_lam_bh, [g["home_score"] for g in b_home], prior_strength)
    post_ab = _gamma_posterior(adj_lam_ab, [g["away_score"] for g in b_home], prior_strength)

    def post_mean(ab): return ab[0] / ab[1]

    print(f"\n  Final posterior lambda means:")
    print(f"    {TEAM_A} home: {TEAM_A} {post_mean(post_ah):.3f}  {TEAM_B} {post_mean(post_ba):.3f}")
    print(f"    {TEAM_B} home: {TEAM_B} {post_mean(post_bh):.3f}  {TEAM_A} {post_mean(post_ab):.3f}")

    # ── Simulate ───────────────────────────────────────────────────────────────
    print(f"\n[4/4] Simulating {n_sims:,} series...")
    result = simulate_series(post_ah, post_ba, post_bh, post_ab, n_sims=n_sims, rng=rng)

    p_a     = result["p_a"]
    p_b     = 1.0 - p_a
    favored = TEAM_A if p_a >= 0.5 else TEAM_B

    print(f"\n{'='*62}")
    print(f"  WALTER CUP FINAL  ·  {TEAM_A} (home ice) vs {TEAM_B}")
    print(f"  {n_sims:,} sims  ·  form_weight={form_weight:.0%}  ·  prior={prior_strength:.0f}")
    print(f"{'='*62}")
    print(f"\n  Series win probability:")
    print(f"    {TEAM_A}:  {p_a*100:5.1f}%   90% CI: [{result['ci_low']*100:.1f}%, {result['ci_high']*100:.1f}%]")
    print(f"    {TEAM_B}:  {p_b*100:5.1f}%")
    print(f"\n  Favored: {favored}")
    print(f"\n  Series length distribution:")
    for length, pct in result["length_dist"].items():
        bar = "#" * int(pct * 40)
        print(f"    {length} games: {pct*100:5.1f}%  {bar}")

    # ── Render ─────────────────────────────────────────────────────────────────
    print(f"\n  Rendering prediction slide...")

    p_a_pct = round(p_a * 100)
    p_b_pct = 100 - p_a_pct
    ci_lo   = round(result["ci_low"]  * 100)
    ci_hi   = round(result["ci_high"] * 100)

    len_dist = result["length_dist"]
    max_pct  = max(round(v * 100) for v in len_dist.values())
    lengths  = [
        {"games": g, "pct": round(f * 100),
         "bar_h": round(round(f * 100) / max_pct * 100) if max_pct else 0}
        for g, f in len_dist.items()
    ]

    lam_ah_v = round(post_mean(post_ah), 2)
    lam_ba_v = round(post_mean(post_ba), 2)
    lam_bh_v = round(post_mean(post_bh), 2)
    lam_ab_v = round(post_mean(post_ab), 2)

    ctx = {
        "badge_label":    "Walter Cup Final",
        "eyebrow":        "2025-26 Playoffs  ·  Walter Cup Final",
        "team_a":         TEAM_A,
        "team_b":         TEAM_B,
        "name_a":         FULL_NAMES[TEAM_A],
        "name_b":         FULL_NAMES[TEAM_B],
        "logo_a":         _logo_uri(TEAM_A),
        "logo_b":         _logo_uri(TEAM_B),
        "favored":        favored,
        "p_a_pct":        p_a_pct,
        "p_b_pct":        p_b_pct,
        "ci_low":         ci_lo,
        "ci_high":        ci_hi,
        "lengths":        lengths,
        "max_pct":        max_pct,
        "lam_a_home":     f"{lam_ah_v:.2f}",
        "lam_b_at_a":     f"{lam_ba_v:.2f}",
        "lam_b_home":     f"{lam_bh_v:.2f}",
        "lam_a_at_b":     f"{lam_ab_v:.2f}",
        "lam_b_home_val": lam_bh_v,
        "lam_a_at_b_val": lam_ab_v,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    render_pred_matchup(ctx, "final_mtl_ott", out_dir=OUTPUT_DIR)
    print(f"\nDone. Slide: {OUTPUT_DIR / 'pred_final_mtl_ott.png'}")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sims",        type=int,   default=50_000)
    parser.add_argument("--form-weight", type=float, default=0.70,
                        help="Weight on Season 9 form vs Season 8 MLE (0=ignore S9, 1=pure S9)")
    parser.add_argument("--prior",       type=float, default=4.0,
                        help="Prior strength for H2H Bayesian update")
    parser.add_argument("--seed",        type=int,   default=None)
    args = parser.parse_args()
    run(n_sims=args.sims, form_weight=args.form_weight,
        prior_strength=args.prior, seed=args.seed)
