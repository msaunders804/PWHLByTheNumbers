"""
run_playoff_predictions.py — Playoff series predictions: MLE vs Bayesian update.

Stage 1 — Dixon-Coles MLE: fits attack/defense parameters from all 120
           regular-season games.  Treats those point estimates as fixed truth.

Stage 2 — Bayesian update: uses the MLE lambdas as a Gamma prior, then
           updates with the 4 head-to-head games for each specific matchup.
           Each simulation independently samples λ from the posterior, so
           parameter uncertainty is propagated into the credible interval.

Matchups:
  MTL vs MIN  (MTL = 1st seed, home ice)
  OTT vs BOS  (OTT = higher seed — adjust MATCHUPS if wrong)

Usage:
  python -m pwhl_btn.jobs.run_playoff_predictions
  python -m pwhl_btn.jobs.run_playoff_predictions --sims 100000
  python -m pwhl_btn.jobs.run_playoff_predictions --prior 5   # down-weight season model
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from pwhl_btn.db.db_config import get_engine
from pwhl_btn.analytics.poisson_model import DixonColesModel
from pwhl_btn.analytics.bayes_update import BayesianMatchupPredictor

SEASON_ID = 8

# PWHL best-of-5: 2-2-1 format.  'A' = higher seed home, 'B' = lower seed home.
BEST_OF_5_SCHEDULE = ["A", "A", "B", "B", "A"]

# (higher_seed, lower_seed)
MATCHUPS = [
    ("MTL", "MIN"),
    ("OTT", "BOS"),
]

engine = get_engine()


def load_season_games() -> list[dict]:
    with Session(engine) as session:
        rows = session.execute(text("""
            SELECT ht.team_code AS home_code, at.team_code AS away_code,
                   g.home_score, g.away_score, g.result_type, g.date
            FROM games g
            JOIN teams ht ON ht.team_id = g.home_team_id AND ht.season_id = :sid
            JOIN teams at ON at.team_id = g.away_team_id AND at.season_id = :sid
            WHERE g.season_id = :sid AND g.game_status = 'final'
            ORDER BY g.date ASC
        """), {"sid": SEASON_ID}).fetchall()
    return [dict(r._mapping) for r in rows]


def load_h2h_games(team_a: str, team_b: str) -> list[dict]:
    with Session(engine) as session:
        rows = session.execute(text("""
            SELECT ht.team_code AS home_code, at.team_code AS away_code,
                   g.home_score, g.away_score, g.result_type, g.date
            FROM games g
            JOIN teams ht ON ht.team_id = g.home_team_id AND ht.season_id = :sid
            JOIN teams at ON at.team_id = g.away_team_id AND at.season_id = :sid
            WHERE g.season_id = :sid AND g.game_status = 'final'
              AND ((ht.team_code = :ta AND at.team_code = :tb)
                OR (ht.team_code = :tb AND at.team_code = :ta))
            ORDER BY g.date ASC
        """), {"sid": SEASON_ID, "ta": team_a, "tb": team_b}).fetchall()
    return [dict(r._mapping) for r in rows]


def _h2h_summary(games: list[dict], team_a: str, team_b: str) -> str:
    a_wins = sum(
        1 for g in games
        if (g["home_code"] == team_a and g["home_score"] > g["away_score"])
        or (g["away_code"] == team_a and g["away_score"] > g["home_score"])
    )
    gf = sum(g["home_score"] if g["home_code"] == team_a else g["away_score"] for g in games)
    ga = sum(g["away_score"] if g["home_code"] == team_a else g["home_score"] for g in games)
    return (f"{team_a} {a_wins}–{len(games)-a_wins}  GF {gf}  GA {ga}  GD {gf-ga:+d}  "
            f"({len(games)} games, {sum(1 for g in games if g['home_code']==team_a)} at home)")


def _h2h_detail(games: list[dict], team_a: str, team_b: str):
    """Print per-game observed goals for each home/away config."""
    a_home = [(g["home_score"], g["away_score"]) for g in games if g["home_code"] == team_a]
    b_home = [(g["home_score"], g["away_score"]) for g in games if g["home_code"] == team_b]
    if a_home:
        ah_gf = sum(s[0] for s in a_home)
        ah_ga = sum(s[1] for s in a_home)
        print(f"    {team_a} home ({len(a_home)}g): {team_a} scored {ah_gf} "
              f"({ah_gf/len(a_home):.2f}/g), {team_b} scored {ah_ga} ({ah_ga/len(a_home):.2f}/g)")
    if b_home:
        bh_gf = sum(s[0] for s in b_home)
        bh_ga = sum(s[1] for s in b_home)
        print(f"    {team_b} home ({len(b_home)}g): {team_b} scored {bh_gf} "
              f"({bh_gf/len(b_home):.2f}/g), {team_a} scored {bh_ga} ({bh_ga/len(b_home):.2f}/g)")


def run(n_sims: int = 50_000, prior_strength: float = 10.0, seed: int | None = None):
    rng = random.Random(seed)

    print(f"\nLoading Season {SEASON_ID} game data...")
    all_games = load_season_games()
    print(f"  {len(all_games)} regular-season games loaded")

    print("\nFitting Dixon-Coles model (Stage 1 — MLE on full season)...")
    model = DixonColesModel()
    model.fit(all_games)
    print(model.summary())

    bayes = BayesianMatchupPredictor(model, prior_strength=prior_strength)

    print(f"\n{'═'*58}")
    print(f"  PLAYOFF PREDICTIONS  ·  {n_sims:,} simulations")
    print(f"  Prior strength: {prior_strength:.0f}  "
          f"(season model ≈ {prior_strength:.0f} equiv. H2H games)")
    print(f"{'═'*58}")

    for team_a, team_b in MATCHUPS:
        h2h = load_h2h_games(team_a, team_b)

        print(f"\n  {'─'*54}")
        print(f"  {team_a} vs {team_b}")
        print(f"  H2H this season:  {_h2h_summary(h2h, team_a, team_b)}")
        _h2h_detail(h2h, team_a, team_b)

        # Stage 1: MLE-only result (uses point-estimate lambdas, no Gamma sampling)
        mle_result = model.simulate_series(
            team_a=team_a,
            team_b=team_b,
            home_schedule=BEST_OF_5_SCHEDULE,
            n_sims=n_sims,
            rng=random.Random(seed),
        )
        print(f"\n  Stage 1 — MLE (season-only):")
        print(f"    {team_a}: {mle_result.p_a_wins*100:.1f}%   "
              f"{team_b}: {mle_result.p_b_wins*100:.1f}%")
        print(f"    λ {team_a} home: {mle_result.probs_a_home['lam_home']:.3f} / "
              f"{mle_result.probs_a_home['lam_away']:.3f}  |  "
              f"{team_b} home: {mle_result.probs_b_home['lam_home']:.3f} / "
              f"{mle_result.probs_b_home['lam_away']:.3f}")

        # Stage 2: Bayesian update
        bayes_result = bayes.simulate_series(
            team_a=team_a,
            team_b=team_b,
            h2h_games=h2h,
            home_schedule=BEST_OF_5_SCHEDULE,
            n_sims=n_sims,
            rng=rng,
        )
        print(bayes_result.summary(mle_p_a=mle_result.p_a_wins))

    print(f"\n  Notes:")
    print(f"  • Gamma conjugate update: exact closed-form posterior, no MCMC")
    print(f"  • CI from {n_sims//100}-simulation chunks — reflects parameter uncertainty")
    print(f"  • Posterior λ means show how H2H evidence shifted the season estimate")
    print(f"  • OT resolved by Bradley-Terry on the sampled λ values")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sims",  type=int,   default=50_000, help="Simulations per matchup")
    parser.add_argument("--prior", type=float, default=10.0,   help="Prior strength (equiv games)")
    parser.add_argument("--seed",  type=int,   default=None,   help="Random seed")
    args = parser.parse_args()
    run(n_sims=args.sims, prior_strength=args.prior, seed=args.seed)
