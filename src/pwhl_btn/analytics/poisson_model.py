"""
poisson_model.py — Dixon-Coles Poisson model for PWHL playoff series prediction.

Fits per-team attack and defense parameters from observed season scorelines via MLE.
Simulates playoff series (best-of-5) using those fitted lambdas rather than a
hand-weighted composite score.

Reference: Dixon & Coles (1997), "Modelling Association Football Scores and
Inefficiencies in the Football Betting Market", JRSS Series C.
"""
from __future__ import annotations

import math
import random
from collections import Counter
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import minimize


# ── Dixon-Coles correction ─────────────────────────────────────────────────────

def _dc_tau(x: int, y: int, lam1: float, lam2: float, rho: float) -> float:
    """
    Correction factor for low-scoring results that are slightly mis-modelled
    by independent Poisson processes.  Only applies to {(0,0),(1,0),(0,1),(1,1)}.
    """
    if x == 0 and y == 0:
        return 1.0 - lam1 * lam2 * rho
    if x == 0 and y == 1:
        return 1.0 + lam1 * rho
    if x == 1 and y == 0:
        return 1.0 + lam2 * rho
    if x == 1 and y == 1:
        return 1.0 - rho
    return 1.0


def _poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam + k * math.log(lam) - math.lgamma(k + 1))


# ── Model ──────────────────────────────────────────────────────────────────────

@dataclass
class DixonColesModel:
    """
    Fitted Dixon-Coles model.  Parameters are stored after calling .fit().

    For a game between home team i and away team j:
      λ_home = exp(home_adv + attack[i] - defense[j])
      λ_away = exp(attack[j] - defense[i])

    Identifiability: attack and defense are anchored to the reference team
    (first alphabetically), whose parameters are fixed at 0.
    """
    teams: list[str] = field(default_factory=list)   # all teams in fitting data
    home_adv:  float = 0.0
    rho:       float = 0.0          # Dixon-Coles low-score correction
    attack:    dict[str, float] = field(default_factory=dict)
    defense:   dict[str, float] = field(default_factory=dict)
    converged: bool = False
    n_games:   int  = 0

    # ── Fitting ───────────────────────────────────────────────────────────────

    def fit(self, games: list[dict]) -> "DixonColesModel":
        """
        Fit the model via MLE.

        games: list of dicts with keys:
          home_code, away_code, home_score, away_score
        """
        self.n_games = len(games)
        self.teams   = sorted({g["home_code"] for g in games} |
                               {g["away_code"] for g in games})
        n = len(self.teams)
        ref = self.teams[0]   # reference team — parameters fixed at 0
        free = self.teams[1:] # n-1 free attack + n-1 free defense params

        # Initial params: [home_adv, rho, attack_1..n-1, defense_1..n-1]
        x0 = np.zeros(2 + 2 * (n - 1))
        x0[0] = 0.25   # typical home advantage in hockey

        def neg_ll(params):
            home_adv = params[0]
            rho      = params[1]
            atk = {ref: 0.0, **{t: params[2 + i]       for i, t in enumerate(free)}}
            dfs = {ref: 0.0, **{t: params[2 + (n-1) + i] for i, t in enumerate(free)}}

            ll = 0.0
            for g in games:
                h, a = g["home_code"], g["away_code"]
                x, y = int(g["home_score"]), int(g["away_score"])
                lam1 = math.exp(home_adv + atk[h] - dfs[a])
                lam2 = math.exp(atk[a] - dfs[h])
                tau  = _dc_tau(x, y, lam1, lam2, rho)
                if tau <= 0:
                    return 1e10
                ll += math.log(tau) + _log_poisson(x, lam1) + _log_poisson(y, lam2)
            return -ll

        # rho: allow small positive values (hockey OT means "draws" may be
        # slightly over-represented vs pure Poisson; cap at 0.15 to keep tau > 0)
        bounds = [(-2, 2), (-0.5, 0.15)] + [(-3, 3)] * (2 * (n - 1))
        result = minimize(neg_ll, x0, method="L-BFGS-B", bounds=bounds,
                          options={"maxiter": 2000, "ftol": 1e-12})

        self.converged = result.success
        self.home_adv  = result.x[0]
        self.rho       = result.x[1]
        self.attack  = {ref: 0.0, **{t: result.x[2 + i]         for i, t in enumerate(free)}}
        self.defense = {ref: 0.0, **{t: result.x[2 + (n-1) + i] for i, t in enumerate(free)}}
        return self

    # ── Game-level prediction ─────────────────────────────────────────────────

    def lambdas(self, home: str, away: str) -> tuple[float, float]:
        """Expected goals for home team and away team over regulation."""
        lam1 = math.exp(self.home_adv + self.attack[home] - self.defense[away])
        lam2 = math.exp(self.attack[away] - self.defense[home])
        return lam1, lam2

    def game_probs(self, home: str, away: str, max_goals: int = 10) -> dict:
        """
        Returns P(home win REG), P(draw→OT), P(away win REG),
        P(home win OT), P(away win OT), and expected goals.
        """
        lam1, lam2 = self.lambdas(home, away)

        p_home_reg = p_draw = p_away_reg = 0.0
        for x in range(max_goals + 1):
            for y in range(max_goals + 1):
                p = _dc_tau(x, y, lam1, lam2, self.rho) * _poisson_pmf(x, lam1) * _poisson_pmf(y, lam2)
                if x > y:
                    p_home_reg += p
                elif x < y:
                    p_away_reg += p
                else:
                    p_draw += p

        # OT: Bradley-Terry on the same lambda rates (neutral attack/defense balance)
        p_home_ot = lam1 / (lam1 + lam2)
        p_away_ot = lam2 / (lam1 + lam2)

        return {
            "lam_home":    round(lam1, 3),
            "lam_away":    round(lam2, 3),
            "p_home_reg":  p_home_reg,
            "p_draw":      p_draw,
            "p_away_reg":  p_away_reg,
            "p_home_ot":   p_home_ot,
            "p_away_ot":   p_away_ot,
            "p_home_win":  p_home_reg + p_draw * p_home_ot,
            "p_away_win":  p_away_reg + p_draw * p_away_ot,
        }

    # ── Series simulation ─────────────────────────────────────────────────────

    def simulate_series(
        self,
        team_a: str,
        team_b: str,
        home_schedule: list[str],  # e.g. ['A','A','B','B','A'] for 2-2-1
        n_sims: int = 50_000,
        rng: random.Random | None = None,
    ) -> "SeriesResult":
        """
        Simulates a playoff series n_sims times.

        team_a is treated as the higher seed.
        home_schedule: list of which team is home for each potential game,
                       length = best_of.  e.g. ['A','A','B','B','A'] for best-of-5.
        """
        if rng is None:
            rng = random.Random()

        best_of   = len(home_schedule)
        wins_to_win = (best_of + 1) // 2

        a_series_wins = 0
        series_lengths: list[int] = []
        game_records: list[list[str]] = []  # per-game winner across all sims

        # Pre-compute game probs for each potential home/away assignment
        probs_a_home = self.game_probs(team_a, team_b)
        probs_b_home = self.game_probs(team_b, team_a)

        for _ in range(n_sims):
            wins_a = wins_b = 0
            game_winners = []
            for g_idx in range(best_of):
                if wins_a == wins_to_win or wins_b == wins_to_win:
                    break
                is_a_home = home_schedule[g_idx] == "A"
                probs     = probs_a_home if is_a_home else probs_b_home
                r = rng.random()
                if is_a_home:
                    a_wins_game = r < probs["p_home_win"]
                else:
                    a_wins_game = r > probs["p_home_win"]  # a is away team here

                if a_wins_game:
                    wins_a += 1
                    game_winners.append(team_a)
                else:
                    wins_b += 1
                    game_winners.append(team_b)

            if wins_a == wins_to_win:
                a_series_wins += 1
            series_lengths.append(wins_a + wins_b)
            game_records.append(game_winners)

        return SeriesResult(
            team_a=team_a,
            team_b=team_b,
            n_sims=n_sims,
            a_series_wins=a_series_wins,
            series_lengths=series_lengths,
            home_schedule=home_schedule,
            probs_a_home=probs_a_home,
            probs_b_home=probs_b_home,
        )

    # ── Diagnostics ───────────────────────────────────────────────────────────

    def summary(self) -> str:
        lines = [
            f"Dixon-Coles Poisson Model  (n_games={self.n_games}, converged={self.converged})",
            f"  home_adv = {self.home_adv:+.4f}  (exp={math.exp(self.home_adv):.3f}x goal rate boost)",
            f"  rho      = {self.rho:+.4f}",
            "",
            f"  {'Team':<8}  {'Attack':>8}  {'Defense':>8}  {'Net':>8}",
            f"  {'─'*40}",
        ]
        for t in sorted(self.teams):
            net = self.attack[t] - self.defense[t]
            lines.append(f"  {t:<8}  {self.attack[t]:+8.4f}  {self.defense[t]:+8.4f}  {net:+8.4f}")
        return "\n".join(lines)


# ── Series result container ────────────────────────────────────────────────────

@dataclass
class SeriesResult:
    team_a:         str
    team_b:         str
    n_sims:         int
    a_series_wins:  int
    series_lengths: list[int]
    home_schedule:  list[str]
    probs_a_home:   dict
    probs_b_home:   dict

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

    def summary(self) -> str:
        best_of = len(self.home_schedule)
        hs = "".join(self.home_schedule)
        lines = [
            f"\n  {'═'*52}",
            f"  {self.team_a} vs {self.team_b}  ·  Best-of-{best_of}  ·  Home: {hs}",
            f"  {'═'*52}",
            f"",
            f"  Series win probability:",
            f"    {self.team_a}:  {self.p_a_wins*100:5.1f}%",
            f"    {self.team_b}:  {self.p_b_wins*100:5.1f}%",
            f"",
            f"  Series length distribution:",
        ]
        for length, pct in self.length_dist.items():
            bar = "█" * int(pct * 40)
            lines.append(f"    {length} games: {pct*100:5.1f}%  {bar}")
        lines.append("")
        lines.append(f"  Per-game win prob (regulation + OT):")

        for g_idx in range(best_of):
            is_a_home = self.home_schedule[g_idx] == "A"
            probs     = self.probs_a_home if is_a_home else self.probs_b_home
            if is_a_home:
                p_a = probs["p_home_win"]
                p_b = probs["p_away_win"]
                loc = f"{self.team_a} home"
            else:
                p_a = probs["p_away_win"]
                p_b = probs["p_home_win"]
                loc = f"{self.team_b} home"
            lines.append(
                f"    Gm {g_idx+1} ({loc}):  "
                f"{self.team_a} {p_a*100:.1f}%  ·  {self.team_b} {p_b*100:.1f}%  "
                f"  [λ {probs['lam_home']:.2f}–{probs['lam_away']:.2f}]"
            )
        return "\n".join(lines)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _log_poisson(k: int, lam: float) -> float:
    if lam <= 0:
        return 0.0 if k == 0 else -1e10
    return -lam + k * math.log(lam) - math.lgamma(k + 1)
