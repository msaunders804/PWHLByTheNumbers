# Playoff Prediction Model: Methodology Documentation

How the PWHL playoff series predictions were conducted, reconstructed from the code in `src/pwhl_btn/analytics/` and `src/pwhl_btn/jobs/`.

---

## 1. Overview

The playoff work is a separate, more rigorous modeling track than the regular-season Monte Carlo. Where the season model uses a weighted composite strength score, the playoff model fits a formal statistical model of goal scoring (Dixon-Coles Poisson) by maximum likelihood, then layers Bayesian updating on top. Three prediction jobs were run as the playoffs progressed, each adapted to the data available at that moment:

| Stage of playoffs | Job | Approach |
|---|---|---|
| Round 1 (MTL vs MIN, OTT vs BOS) | `run_playoff_predictions.py` | Dixon-Coles MLE on 120 regular-season games, then Bayesian H2H update per matchup |
| Walter Cup Final (MTL vs OTT), playoff form only | `run_playoff_mc.py` | Dixon-Coles refit on only the 9 playoff games |
| Walter Cup Final, full model | `run_final_prediction.py` | Four-stage blend: season MLE + playoff form adjustment + H2H Bayesian update + posterior simulation |

All three simulate the best-of-5 series under the PWHL's 2-2-1 home format (`AABBA`, higher seed home for games 1, 2, 5), 50,000 iterations by default.

---

## 2. Data

Game results come from the project's Railway MySQL database (populated from the PWHL HockeyTech API), queried with raw SQL through SQLAlchemy. The relevant inputs are final scores, result type (REG/OT/SO), home/away assignment, and date, for Season 8 (regular season, 120 games) and Season 9 (playoffs). A noted DB quirk is handled explicitly: Season 8 `teams` rows only contain expansion teams, so the four playoff teams' IDs are resolved from Season 9 (team IDs are league-wide).

---

## 3. Core engine: the Dixon-Coles Poisson model (`poisson_model.py`)

This is the foundation, following Dixon and Coles (1997), the standard reference for score-based sports prediction.

**Parameterization.** Every team gets an attack parameter and a defense parameter. For home team i hosting away team j, expected goals are:

    lambda_home = exp(home_adv + attack_i - defense_j)
    lambda_away = exp(attack_j - defense_i)

Goals are modeled as Poisson with those rates. A shared `home_adv` term captures home ice. For identifiability, the first team alphabetically is anchored at attack = defense = 0, so with n teams there are 2(n-1) + 2 free parameters.

**The Dixon-Coles correction.** Independent Poissons slightly mis-model low-scoring games. A correction factor tau(x, y, rho) adjusts the joint probability of the scorelines (0,0), (1,0), (0,1), (1,1). The correlation parameter rho is bounded at [-0.5, 0.15]; the positive cap was chosen deliberately because hockey OT means regulation draws are slightly over-represented relative to pure Poisson.

**Fitting.** Parameters are estimated by maximizing the log-likelihood sum of log tau + log Poisson(home goals) + log Poisson(away goals) over all games, using scipy's L-BFGS-B with bounds (home_adv in [-2, 2], attack/defense in [-3, 3]), initialized at home_adv = 0.25 (typical hockey value). Numerically stable log-PMFs use `lgamma` rather than factorials. Convergence status is stored and reported.

**Single-game probabilities.** `game_probs()` enumerates the score grid (0 to 10 goals each side), applying tau to each cell, to get P(home wins in regulation), P(draw after regulation), and P(away wins in regulation). Regulation draws are resolved by a Bradley-Terry split on the same lambdas: P(home wins OT) = lambda_home / (lambda_home + lambda_away). Total win probability = regulation win + draw share times OT win.

**Series simulation.** `simulate_series()` plays the best-of-5 game by game. Game probabilities are precomputed for both home/away configurations, the series ends when a team reaches 3 wins, and 50,000 replays produce the series win probability and the distribution of series lengths (3, 4, or 5 games).

---

## 4. Bayesian head-to-head update (`bayes_update.py`)

The MLE gives point estimates of lambda derived from all 120 regular-season games. Those estimates are treated as a prior belief, then updated with the head-to-head games for the specific matchup, using the Gamma-Poisson conjugate pair, which has an exact closed-form posterior:

    Prior:      lambda ~ Gamma(shape = prior_strength * lambda_mle, rate = prior_strength)
    Likelihood: goals_1 ... goals_n ~ Poisson(lambda)
    Posterior:  lambda ~ Gamma(shape + sum(goals), rate + n)

This is done separately for four configurations: A's goals at home, B's goals at A, B's goals at home, A's goals at B, using only the H2H games in each configuration.

`prior_strength` is the single interpretability knob: it equals the number of pseudo-games of evidence the season model is worth. Low (~3) lets H2H data dominate; ~10 (the default) balances; high (~30) collapses back toward the pure MLE.

**The propagation step, which is the key design decision:** each of the 50,000 series simulations independently samples fresh lambda values from the four posterior Gammas (`random.gammavariate`), then plays the series with Poisson goal draws and Bradley-Terry OT. Because lambda itself varies across iterations, parameter uncertainty flows into the final series probabilities rather than being ignored.

**Credible interval.** The 50,000 sims are split into 100 chunks of 500; each chunk's win rate is recorded, and the 5th and 95th percentiles of the chunk rates form a 90% interval reported alongside the point probability.

---

## 5. Round 1 predictions (`run_playoff_predictions.py`)

For MTL vs MIN and OTT vs BOS, the job ran both models side by side as an explicit comparison:

Stage 1 fits Dixon-Coles on all 120 Season 8 games and simulates each series from the fixed MLE lambdas. Stage 2 runs the Bayesian predictor, updating those lambdas with the 4 regular-season H2H games per matchup, and reports the shift in series probability versus the MLE as well as the credible interval. The output includes per-game win probabilities for every game of the 2-2-1 schedule with their lambdas.

---

## 6. Walter Cup Final: two complementary models

MTL and OTT had not played each other in the playoffs, so no playoff H2H data existed. Two models were run to triangulate.

**Model A: playoff form only (`run_playoff_mc.py`).** Dixon-Coles is refit from scratch on only the 9 playoff games (OTT vs BOS in 4, MTL vs MIN in 5). Relative strength is inferred transitively through each team's round 1 opponent. Because 9 games is a very small sample for 8+ parameters, the lambdas are wrapped in Gamma priors with prior_strength = 3 and no observations, so the posterior equals the prior. This adds no new data; it deliberately injects sampling uncertainty so the Monte Carlo produces an honest, wide credible interval rather than false confidence.

**Model B: four-stage blended model (`run_final_prediction.py`).** The flagship prediction:

Stage 1: Dixon-Coles MLE on all 120 Season 8 regular-season games establishes baseline attack/defense for all 8 teams.

Stage 2: Playoff form adjustment. For each finalist, actual playoff goals scored and allowed are compared with what the Season 8 model expected in those exact games: attack_factor = observed scored / expected scored, defense_factor = expected allowed / observed allowed. The matchup lambdas are then blended multiplicatively, lambda_adjusted = lambda * (1 - w + w * factor), with form_weight w = 0.70, so playoff form gets 70% of the say.

Stage 3: Bayesian Gamma-Poisson update using the 4 Season 8 MTL vs OTT head-to-head games, with the form-adjusted lambdas as the prior mean.

Stage 4: 50,000 best-of-5 simulations sampling lambda from the posteriors each iteration, producing the series probability, 90% credible interval, and length distribution.

---

## 7. Outputs

Each job prints a full diagnostic report (fitted parameters, lambdas per configuration, posterior vs MLE comparison, length distribution with ASCII histograms) and renders an Instagram-format prediction slide via Jinja2 + Playwright (`render_pred_matchup`), which was published to the ByTheNumbers TikTok/Instagram audience. CLI flags expose the key assumptions (`--sims`, `--prior`, `--form-weight`, `--seed`) so sensitivity checks are one command away.

---

## 8. Limitations to acknowledge if asked

Be ready to discuss these; knowing them is a strength.

The 9-game playoff-only fit is heavily over-parameterized (roughly 10 parameters, 9 observations); the model handles this honestly via the wide prior, but the point estimates themselves should not be trusted, and the code comments say as much. The chunked credible interval is a pragmatic approximation, not a formal posterior interval; a Beta posterior on the win count or proper quantiles of the posterior predictive would be cleaner. The form factors in Stage 2 are an ad hoc multiplicative blend rather than a refit, and form_weight = 0.70 is a judgment call, though it is exposed as a CLI parameter. OT is resolved by Bradley-Terry on regulation scoring rates, ignoring that 3-on-3 OT is a different game state. Four H2H games is thin evidence, which is exactly why the conjugate framework with an explicit prior_strength was the right tool. Finally, `DixonColesModel.simulate_series` uses fixed MLE probabilities (no parameter uncertainty), which is precisely the deficiency the Bayesian path was built to fix; presenting both side by side in Round 1 was good methodology.
