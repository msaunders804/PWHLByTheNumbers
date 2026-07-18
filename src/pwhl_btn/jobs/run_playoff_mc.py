"""
run_playoff_mc.py — Walter Cup Final Monte Carlo: playoff data only.

Fits Dixon-Coles on the 9 Season 9 playoff games (OTT vs BOS x4,
MTL vs MIN x5) and runs a straight Monte Carlo simulation.  No H2H
Bayesian update — MTL and OTT have not played each other yet.

The model infers relative strength by comparing how each team performed
vs their R1 opponent; home advantage is estimated from those same games.

Usage:
  python -m pwhl_btn.jobs.run_playoff_mc
  python -m pwhl_btn.jobs.run_playoff_mc --sims 100000
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
from pwhl_btn.analytics.bayes_update import _sample_gamma, _poisson_sample, _gamma_posterior
from pwhl_btn.render.prediction_render import render_pred_matchup

SEASON_9 = 9

TEAM_A = "MTL"
TEAM_B = "OTT"

BEST_OF_5 = ["A", "A", "B", "B", "A"]

FULL_NAMES = {
    "MTL": "Montréal Victoire",
    "OTT": "Ottawa Charge",
}

OUTPUT_DIR = Path(__file__).resolve().parents[3] / "src" / "pwhl_btn" / "render" / "output"

engine = get_engine(pool_pre_ping=True)


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


def run(n_sims: int = 50_000, prior_strength: float = 3.0, seed: int | None = None):
    rng = random.Random(seed)

    print(f"\nWalter Cup Final — Playoff-Only Monte Carlo")
    print("=" * 52)

    print(f"\n[1/3] Loading Season 9 playoff games...")
    games = _load_s9_games()
    print(f"  {len(games)} games across 2 series")
    for g in games:
        winner = g["home_code"] if g["home_score"] > g["away_score"] else g["away_code"]
        print(f"    {g['date']}  {g['home_code']} {g['home_score']}-{g['away_score']} "
              f"{g['away_code']}  ({g['result_type']})  W:{winner}")

    print(f"\n[2/3] Fitting Dixon-Coles on Season 9 data only...")
    model = DixonColesModel()
    model.fit(games)
    print(model.summary())

    lam_ah, lam_ba = model.lambdas(TEAM_A, TEAM_B)
    lam_bh, lam_ab = model.lambdas(TEAM_B, TEAM_A)

    print(f"\n  Matchup lambdas (playoff MLE):")
    print(f"    {TEAM_A} home: {TEAM_A} {lam_ah:.3f} xG  /  {TEAM_B} {lam_ba:.3f} xG")
    print(f"    {TEAM_B} home: {TEAM_B} {lam_bh:.3f} xG  /  {TEAM_A} {lam_ab:.3f} xG")
    print(f"\n  Team parameters:")
    for t in sorted(model.teams):
        net = model.attack[t] - model.defense[t]
        print(f"    {t:<5}  atk {model.attack[t]:+.3f}  def {model.defense[t]:+.3f}  net {net:+.3f}")

    # Bayesian simulation — prior_strength=3 reflects small sample uncertainty
    post_ah = _gamma_posterior(lam_ah, [], prior_strength)
    post_ba = _gamma_posterior(lam_ba, [], prior_strength)
    post_bh = _gamma_posterior(lam_bh, [], prior_strength)
    post_ab = _gamma_posterior(lam_ab, [], prior_strength)

    print(f"\n[3/3] Monte Carlo: {n_sims:,} simulations (prior_strength={prior_strength:.0f})...")

    wins_to_win    = 3
    ci_chunks      = 100
    chunk_size     = max(1, n_sims // ci_chunks)
    a_series_wins  = 0
    series_lengths = []
    chunk_rates:   list[float] = []
    chunk_wins     = 0
    chunk_count    = 0

    for _ in range(n_sims):
        s_ah = _sample_gamma(*post_ah, rng)
        s_ba = _sample_gamma(*post_ba, rng)
        s_bh = _sample_gamma(*post_bh, rng)
        s_ab = _sample_gamma(*post_ab, rng)

        wins_a = wins_b = 0
        for g_idx in range(len(BEST_OF_5)):
            if wins_a == wins_to_win or wins_b == wins_to_win:
                break
            is_a_home = BEST_OF_5[g_idx] == "A"
            lh, la = (s_ah, s_ba) if is_a_home else (s_bh, s_ab)
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
    ci_low   = sorted_rates[max(0, int(n_ch * 0.05))]
    ci_high  = sorted_rates[min(n_ch - 1, int(n_ch * 0.95))]
    len_dist = Counter(series_lengths)
    total    = sum(len_dist.values())
    length_dist = {k: len_dist[k] / total for k in sorted(len_dist)}

    p_a     = a_series_wins / n_sims
    p_b     = 1.0 - p_a
    favored = TEAM_A if p_a >= 0.5 else TEAM_B

    print(f"\n{'='*52}")
    print(f"  PLAYOFF-ONLY MONTE CARLO  ·  {TEAM_A} vs {TEAM_B}")
    print(f"{'='*52}")
    print(f"\n  Series win probability:")
    print(f"    {TEAM_A}:  {p_a*100:5.1f}%   90% CI: [{ci_low*100:.1f}%, {ci_high*100:.1f}%]")
    print(f"    {TEAM_B}:  {p_b*100:5.1f}%")
    print(f"\n  Favored: {favored}")
    print(f"\n  Series length distribution:")
    for length, pct in length_dist.items():
        bar = "#" * int(pct * 40)
        print(f"    {length} games: {pct*100:5.1f}%  {bar}")

    # ── Render ─────────────────────────────────────────────────────────────────
    print(f"\n  Rendering playoff-only Monte Carlo slide...")

    p_a_pct = round(p_a * 100)
    p_b_pct = 100 - p_a_pct
    ci_lo   = round(ci_low  * 100)
    ci_hi   = round(ci_high * 100)

    max_pct = max(round(v * 100) for v in length_dist.values())
    lengths = [
        {"games": g, "pct": round(f * 100),
         "bar_h": round(round(f * 100) / max_pct * 100) if max_pct else 0}
        for g, f in length_dist.items()
    ]

    def post_mean(ab): return ab[0] / ab[1]

    lam_ah_v = round(post_mean(post_ah), 2)
    lam_ba_v = round(post_mean(post_ba), 2)
    lam_bh_v = round(post_mean(post_bh), 2)
    lam_ab_v = round(post_mean(post_ab), 2)

    ctx = {
        "badge_label":    "Walter Cup Final",
        "eyebrow":        "2025-26 Playoffs  ·  Playoff Form Only",
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
    render_pred_matchup(ctx, "final_mtl_ott_playoff_mc", out_dir=OUTPUT_DIR)
    print(f"\nDone. Slide: {OUTPUT_DIR / 'pred_final_mtl_ott_playoff_mc.png'}")
    return p_a, ci_low, ci_high, length_dist


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sims",  type=int,   default=50_000)
    parser.add_argument("--prior", type=float, default=3.0,
                        help="Prior strength — controls CI width given small sample (9 games)")
    parser.add_argument("--seed",  type=int,   default=None)
    args = parser.parse_args()
    run(n_sims=args.sims, prior_strength=args.prior, seed=args.seed)
