"""
bayes_update.py — Bayesian Gamma-Poisson update for playoff matchup prediction.

The Dixon-Coles MLE gives us point estimates of (λ_home, λ_away) for each
home/away configuration.  That estimate is derived from all 120 regular-season
games — it's our prior belief about how these teams perform.

We then update those priors with the head-to-head game data for this specific
matchup using the Gamma-Poisson conjugate pair:

    Prior:     λ ~ Gamma(α₀, β₀)          [shape, rate]
               α₀ = prior_strength × λ_mle
               β₀ = prior_strength
               → E[λ] = λ_mle, Var[λ] = λ_mle / prior_strength

    Likelihood: goals_1, ..., goals_n ~ Poisson(λ)

    Posterior: λ | data ~ Gamma(α₀ + Σgoals, β₀ + n)   [exact, closed-form]
               → E[λ] = (α₀ + Σgoals) / (β₀ + n)

prior_strength controls the tradeoff:
  • Low  (~3):  H2H data almost entirely drives the estimate — high variance
  • Mid  (~10): Balanced blend of season form and H2H evidence
  • High (~30): Season-wide model dominates — close to pure MLE result

During simulation each iteration independently samples λ values from the
posterior Gamma, then draws Poisson goals.  This propagates full parameter
uncertainty into the series win probability and credible interval.
"""
from __future__ import annotations

import math
import random
from collections import Counter
from dataclasses import dataclass, field

from pwhl_btn.analytics.poisson_model import DixonColesModel


# ── Helpers ────────────────────────────────────────────────────────────────────

def _gamma_posterior(prior_lam: float, observed_goals: list[int],
                     prior_strength: float) -> tuple[float, float]:
    """
    Returns (alpha_post, beta_post) — shape and rate of the posterior Gamma.

    Prior:     Gamma(shape = prior_strength * prior_lam,  rate = prior_strength)
    Posterior: Gamma(shape = alpha_prior + sum(goals),    rate = beta_prior + n)
    """
    alpha = prior_strength * prior_lam + sum(observed_goals)
    beta  = prior_strength + len(observed_goals)
    return alpha, beta


def _sample_gamma(alpha: float, beta_rate: float, rng: random.Random) -> float:
    """Sample from Gamma(shape=alpha, rate=beta_rate). Always returns > 0."""
    return max(rng.gammavariate(alpha, 1.0 / beta_rate), 0.01)


def _poisson_sample(lam: float, rng: random.Random) -> int:
    """Knuth's algorithm — exact Poisson sampler."""
    if lam <= 0:
        return 0
    L, k, p = math.exp(-lam), 0, 1.0
    while p > L:
        k += 1
        p *= rng.random()
    return k - 1


# ── Result container ───────────────────────────────────────────────────────────

@dataclass
class BayesianSeriesResult:
    team_a:           str
    team_b:           str
    n_sims:           int
    prior_strength:   float
    a_series_wins:    int
    series_lengths:   list[int]
    home_schedule:    list[str]

    # Posterior parameters for each config (for reporting)
    post_a_home:   tuple[float, float] = (0.0, 0.0)   # (alpha, beta) when A is home
    post_b_at_a:   tuple[float, float] = (0.0, 0.0)   # B goals when A is home
    post_b_home:   tuple[float, float] = (0.0, 0.0)   # when B is home
    post_a_at_b:   tuple[float, float] = (0.0, 0.0)   # A goals when B is home

    # MLE comparison
    mle_lam_a_home: float = 0.0
    mle_lam_b_at_a: float = 0.0
    mle_lam_b_home: float = 0.0
    mle_lam_a_at_b: float = 0.0

    # Credible interval (computed post-hoc from chunked sims)
    ci_low:  float = 0.0
    ci_high: float = 0.0

    @property
    def p_a_wins(self) -> float:
        return self.a_series_wins / self.n_sims

    @property
    def p_b_wins(self) -> float:
        return 1.0 - self.p_a_wins

    @property
    def length_dist(self) -> dict[int, float]:
        c = Counter(self.series_lengths)
        return {k: c[k] / self.n_sims for k in sorted(c)}

    def _post_mean(self, ab: tuple[float, float]) -> float:
        return ab[0] / ab[1]

    def summary(self, mle_p_a: float | None = None) -> str:
        best_of = len(self.home_schedule)
        hs = "".join(self.home_schedule)
        lines = [
            f"\n  ╔{'═'*54}╗",
            f"  ║  {self.team_a} vs {self.team_b}  ·  Best-of-{best_of}  ·  Home: {hs}  ║",
            f"  ╚{'═'*54}╝",
            f"",
            f"  Series win probability  (prior_strength = {self.prior_strength:.0f})",
            f"    {self.team_a}:  {self.p_a_wins*100:5.1f}%   90% CI: [{self.ci_low*100:.1f}%, {self.ci_high*100:.1f}%]",
            f"    {self.team_b}:  {self.p_b_wins*100:5.1f}%",
        ]

        if mle_p_a is not None:
            shift = (self.p_a_wins - mle_p_a) * 100
            direction = "↑" if shift >= 0 else "↓"
            lines.append(f"")
            lines.append(f"  Shift from MLE (season-only):  {self.team_a} {direction} {abs(shift):.1f}pp")

        lines += [
            f"",
            f"  Series length distribution:",
        ]
        for length, pct in self.length_dist.items():
            bar = "█" * int(pct * 40)
            lines.append(f"    {length} games: {pct*100:5.1f}%  {bar}")

        lines += [
            f"",
            f"  Posterior λ (mean)  vs  MLE λ  [home goals / away goals]",
            f"    Config            Posterior     MLE",
            f"    {'─'*48}",
        ]

        cfg_a = f"{self.team_a} home"
        cfg_b = f"{self.team_b} home"
        lines.append(
            f"    {cfg_a:<18}  "
            f"{self._post_mean(self.post_a_home):.3f} / {self._post_mean(self.post_b_at_a):.3f}   "
            f"  {self.mle_lam_a_home:.3f} / {self.mle_lam_b_at_a:.3f}"
        )
        lines.append(
            f"    {cfg_b:<18}  "
            f"{self._post_mean(self.post_b_home):.3f} / {self._post_mean(self.post_a_at_b):.3f}   "
            f"  {self.mle_lam_b_home:.3f} / {self.mle_lam_a_at_b:.3f}"
        )

        return "\n".join(lines)


# ── Predictor ──────────────────────────────────────────────────────────────────

class BayesianMatchupPredictor:
    """
    Wraps a fitted DixonColesModel and applies Gamma conjugate updates
    from head-to-head game data for a specific playoff matchup.
    """

    def __init__(self, model: DixonColesModel, prior_strength: float = 10.0):
        self.model          = model
        self.prior_strength = prior_strength

    def simulate_series(
        self,
        team_a:        str,          # higher seed
        team_b:        str,
        h2h_games:     list[dict],   # all H2H games this season
        home_schedule: list[str],    # e.g. ['A','A','B','B','A']
        n_sims:        int = 50_000,
        rng:           random.Random | None = None,
        ci_chunks:     int = 100,    # how many chunks for credible interval
    ) -> BayesianSeriesResult:

        if rng is None:
            rng = random.Random()

        # Split H2H games by which team is at home
        a_home_games = [g for g in h2h_games if g["home_code"] == team_a]
        b_home_games = [g for g in h2h_games if g["home_code"] == team_b]

        # MLE prior lambdas from the season-wide model
        mle_lam_ah, mle_lam_ba = self.model.lambdas(team_a, team_b)  # A home
        mle_lam_bh, mle_lam_ab = self.model.lambdas(team_b, team_a)  # B home

        # H2H observed goals per configuration
        a_goals_at_home = [g["home_score"] for g in a_home_games]
        b_goals_at_a    = [g["away_score"] for g in a_home_games]
        b_goals_at_home = [g["home_score"] for g in b_home_games]
        a_goals_at_b    = [g["away_score"] for g in b_home_games]

        # Posterior Gamma parameters (shape, rate)
        post_ah = _gamma_posterior(mle_lam_ah, a_goals_at_home, self.prior_strength)
        post_ba = _gamma_posterior(mle_lam_ba, b_goals_at_a,    self.prior_strength)
        post_bh = _gamma_posterior(mle_lam_bh, b_goals_at_home, self.prior_strength)
        post_ab = _gamma_posterior(mle_lam_ab, a_goals_at_b,    self.prior_strength)

        # Simulate
        best_of     = len(home_schedule)
        wins_to_win = (best_of + 1) // 2
        chunk_size  = max(1, n_sims // ci_chunks)

        a_series_wins  = 0
        series_lengths = []
        chunk_rates:   list[float] = []
        chunk_wins  = 0
        chunk_count = 0

        for i in range(n_sims):
            # Sample λ from posteriors — this is the Bayesian propagation step
            lam_ah = _sample_gamma(*post_ah, rng)
            lam_ba = _sample_gamma(*post_ba, rng)
            lam_bh = _sample_gamma(*post_bh, rng)
            lam_ab = _sample_gamma(*post_ab, rng)

            wins_a = wins_b = 0
            for g_idx in range(best_of):
                if wins_a == wins_to_win or wins_b == wins_to_win:
                    break

                is_a_home = home_schedule[g_idx] == "A"
                lam_home, lam_away = (lam_ah, lam_ba) if is_a_home else (lam_bh, lam_ab)

                home_goals = _poisson_sample(lam_home, rng)
                away_goals = _poisson_sample(lam_away, rng)

                if home_goals == away_goals:
                    # OT: winner by rate ratio (Bradley-Terry on sampled lambdas)
                    home_wins_ot = rng.random() < lam_home / (lam_home + lam_away)
                    home_wins_game = home_wins_ot
                else:
                    home_wins_game = home_goals > away_goals

                a_wins_game = home_wins_game if is_a_home else not home_wins_game
                if a_wins_game:
                    wins_a += 1
                else:
                    wins_b += 1

            a_won = wins_a == wins_to_win
            if a_won:
                a_series_wins += 1
                chunk_wins    += 1
            series_lengths.append(wins_a + wins_b)

            chunk_count += 1
            if chunk_count == chunk_size:
                chunk_rates.append(chunk_wins / chunk_size)
                chunk_wins  = 0
                chunk_count = 0

        # 90% credible interval from chunk win rates
        sorted_rates = sorted(chunk_rates)
        n_chunks = len(sorted_rates)
        ci_low  = sorted_rates[max(0, int(n_chunks * 0.05))]
        ci_high = sorted_rates[min(n_chunks - 1, int(n_chunks * 0.95))]

        return BayesianSeriesResult(
            team_a=team_a,
            team_b=team_b,
            n_sims=n_sims,
            prior_strength=self.prior_strength,
            a_series_wins=a_series_wins,
            series_lengths=series_lengths,
            home_schedule=home_schedule,
            post_a_home=post_ah,
            post_b_at_a=post_ba,
            post_b_home=post_bh,
            post_a_at_b=post_ab,
            mle_lam_a_home=mle_lam_ah,
            mle_lam_b_at_a=mle_lam_ba,
            mle_lam_b_home=mle_lam_bh,
            mle_lam_a_at_b=mle_lam_ab,
            ci_low=ci_low,
            ci_high=ci_high,
        )
