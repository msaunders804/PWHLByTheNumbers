"""
monte_carlo.py — PWHL playoff probability simulation.

Simulates the remaining season schedule N times to estimate:
  - Playoff clinch probability (top 4 of 8 teams)
  - Walter Cup probability (1st place finish)
  - Expected final point total (mean ± std dev)

Win probability model (per game):
  strength(team) = 0.35 * pts_pct
                 + 0.30 * rank_score_norm
                 + 0.20 * last5_gd_norm
                 + 0.15 * home_win_pct

  win_prob(home vs away) = strength_home / (strength_home + strength_away)

Usage:
    python pwhl/monte_carlo.py                  # run simulation, print results
    python pwhl/monte_carlo.py --n 10000        # set simulation count
    python pwhl/monte_carlo.py --validate       # backtest against Season 2 midpoint
    python pwhl/monte_carlo.py --export         # write results to output/monte_carlo.json
"""

import argparse
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev

from pwhl_btn.db.db_queries import get_remaining_schedule, get_simulation_inputs

BASE_DIR    = Path(__file__).resolve().parent.parent
OUTPUT_DIR  = BASE_DIR / "output"
PLAYOFF_SPOTS = 4
DEFAULT_N     = 10_000

# Load regression-derived weights if available, else use manual defaults
_WEIGHTS_FILE = Path(__file__).resolve().parent / "weights.json"
if _WEIGHTS_FILE.exists():
    with open(_WEIGHTS_FILE) as _wf:
        _w = json.load(_wf).get("weights", {})
    WEIGHTS = {
        "pts_pct":      _w.get("pts_pct",      0.25),
        "rank_score":   _w.get("rank_score",    0.15),
        "last5_gd":     _w.get("last5_gd",      0.10),
        "home_win_pct": _w.get("home_win_pct",  0.05),
        "sv_pct":       _w.get("sv_pct",        0.15),
        "shots_ratio":  _w.get("shots_ratio",   0.15),
        "xg_ratio":     _w.get("xg_ratio",      0.15),
    }
    print(f"  [weights] Loaded from weights.json (regression-derived)")
else:
    WEIGHTS = {
        "pts_pct":      0.25,
        "rank_score":   0.15,
        "last5_gd":     0.10,
        "home_win_pct": 0.05,
        "sv_pct":       0.15,
        "shots_ratio":  0.15,
        "xg_ratio":     0.15,
    }
    print(f"  [weights] Using manual defaults (run derive_weights.py --save to derive)")


# ── Normalization ──────────────────────────────────────────────────────────────

def _normalize(teams: dict, key: str) -> dict[int, float]:
    """
    Min-max normalize a given key across all teams.
    Returns dict of team_id → normalized value in [0, 1].
    If all values are equal, returns 0.5 for all.
    """
    values = {tid: t[key] for tid, t in teams.items()}
    lo, hi = min(values.values()), max(values.values())
    if hi == lo:
        return {tid: 0.5 for tid in values}
    return {tid: (v - lo) / (hi - lo) for tid, v in values.items()}


def build_strength_map(teams: dict) -> dict[int, float]:
    """
    Computes a composite strength score for each team, normalized 0→1.

    Weights:
      30% — points percentage (recency-blended season quality baseline)
      20% — power ranking score (streak + ppg + last5_gd)
      15% — last 5 goal differential (recent momentum)
      10% — home win percentage
      15% — team SV% (goalie quality — strong predictor in low-scoring leagues)
      10% — shots ratio (possession/shot quality proxy)
    """
    norm_pts_pct      = _normalize(teams, "pts_pct")
    norm_rank_score   = _normalize(teams, "rank_score")
    norm_last5_gd     = _normalize(teams, "last5_gd")
    norm_home_win_pct = _normalize(teams, "home_win_pct")
    norm_sv_pct       = _normalize(teams, "sv_pct")      if all("sv_pct"      in t for t in teams.values()) else {tid: 0.5 for tid in teams}
    norm_shots_ratio  = _normalize(teams, "shots_ratio") if all("shots_ratio" in t for t in teams.values()) else {tid: 0.5 for tid in teams}
    norm_xg_ratio     = _normalize(teams, "xg_ratio")    if all("xg_ratio"    in t for t in teams.values()) else {tid: 0.5 for tid in teams}

    strength = {}
    for tid in teams:
        strength[tid] = (
            WEIGHTS["pts_pct"]      * norm_pts_pct[tid]
          + WEIGHTS["rank_score"]   * norm_rank_score[tid]
          + WEIGHTS["last5_gd"]     * norm_last5_gd[tid]
          + WEIGHTS["home_win_pct"] * norm_home_win_pct[tid]
          + WEIGHTS["sv_pct"]       * norm_sv_pct[tid]
          + WEIGHTS["shots_ratio"]  * norm_shots_ratio[tid]
          + WEIGHTS["xg_ratio"]     * norm_xg_ratio[tid]
        )
    # Clamp to avoid 0 (would cause division by zero in win_prob)
    return {tid: max(s, 0.01) for tid, s in strength.items()}


def win_prob(home_tid: int, away_tid: int, strength: dict[int, float]) -> float:
    """
    Returns probability that the home team wins.
    Home team gets a passive advantage through home_win_pct being baked
    into their strength score already.
    """
    s_home = strength[home_tid]
    s_away = strength[away_tid]
    return s_home / (s_home + s_away)


# ── Single simulation run ──────────────────────────────────────────────────────

# PWHL season average goals per game (used to scale Poisson lambdas)
PWHL_AVG_GPG = 2.8   # league average goals per team per game

def _poisson_sample(lam: float, rng: random.Random) -> int:
    """
    Samples from a Poisson distribution using Knuth's algorithm.
    lam: expected number of goals (lambda).
    Returns integer goals scored.
    """
    if lam <= 0:
        return 0
    L = math.exp(-lam)
    k, p = 0, 1.0
    while p > L:
        k += 1
        p *= rng.random()
    return k - 1


def simulate_once(
    remaining_games: list[dict],
    current_pts:     dict[int, int],
    strength:        dict[int, float],
    rng:             random.Random,
) -> dict[int, int]:
    """
    Simulates all remaining games once using Poisson goal scoring.

    For each game:
      - Home team lambda = PWHL_AVG_GPG * (s_home / avg_strength) * HOME_BOOST
      - Away team lambda = PWHL_AVG_GPG * (s_away / avg_strength)
      - Goals drawn independently from Poisson(lambda)
      - Ties go to OT: 50/50 winner, loser gets 1 pt (OTL)

    Returns dict of team_id → final total points.
    """
    pts = dict(current_pts)
    HOME_BOOST   = 1.08   # ~8% more goals at home, consistent with PWHL data
    avg_strength = mean(strength.values()) if strength else 1.0

    for game in remaining_games:
        h = game["home_team_id"]
        a = game["away_team_id"]

        if h not in strength or a not in strength:
            continue

        lam_h = PWHL_AVG_GPG * (strength[h] / avg_strength) * HOME_BOOST
        lam_a = PWHL_AVG_GPG * (strength[a] / avg_strength)

        goals_h = _poisson_sample(max(lam_h, 0.3), rng)
        goals_a = _poisson_sample(max(lam_a, 0.3), rng)

        if goals_h > goals_a:
            pts[h] = pts.get(h, 0) + 2
        elif goals_a > goals_h:
            pts[a] = pts.get(a, 0) + 2
        else:
            # Tied after regulation → OT: 50/50, loser gets 1 pt
            if rng.random() < 0.5:
                pts[h] = pts.get(h, 0) + 2
                pts[a] = pts.get(a, 0) + 1
            else:
                pts[a] = pts.get(a, 0) + 2
                pts[h] = pts.get(h, 0) + 1

    return pts


# ── Main simulation ────────────────────────────────────────────────────────────

def run_simulation(n: int = DEFAULT_N) -> dict:
    """
    Runs the full Monte Carlo simulation n times.

    Returns:
        {
          team_id: {
            "team_code":       str,
            "current_pts":     int,
            "games_remaining": int,
            "playoff_pct":     float,   # 0–100
            "walter_cup_pct":  float,   # 0–100
            "proj_pts_mean":   float,
            "proj_pts_std":    float,
            "proj_pts_low":    int,     # 10th percentile
            "proj_pts_high":   int,     # 90th percentile
          }
        }
    """
    print(f"  Loading simulation inputs...")
    teams     = get_simulation_inputs()
    remaining = get_remaining_schedule()

    if not teams:
        raise ValueError("No team data found — is the DB populated?")
    if not remaining:
        print("  ⚠️  No remaining games found — season may be complete")

    print(f"  Teams: {len(teams)} | Remaining games: {len(remaining)} | Simulations: {n:,}")

    strength     = build_strength_map(teams)
    current_pts  = {tid: t["pts"] for tid, t in teams.items()}

    # Accumulators
    playoff_counts    = defaultdict(int)
    walter_cup_counts = defaultdict(int)
    pts_accumulator   = defaultdict(list)

    rng = random.Random()

    for i in range(n):
        final_pts = simulate_once(remaining, current_pts, strength, rng)

        # Rank teams by final points (ties broken randomly — no tiebreaker data)
        ranked = sorted(final_pts.items(), key=lambda x: (x[1], rng.random()), reverse=True)

        for rank, (tid, pts) in enumerate(ranked):
            pts_accumulator[tid].append(pts)
            if rank < PLAYOFF_SPOTS:
                playoff_counts[tid] += 1
            if rank == 0:
                walter_cup_counts[tid] += 1

    # Build results
    results = {}
    for tid, t in teams.items():
        all_pts = pts_accumulator[tid]
        results[tid] = {
            "team_code":        t["team_code"],
            "current_pts":      t["pts"],
            "games_remaining":  t["games_remaining"],
            "playoff_pct":      round(playoff_counts[tid]    / n * 100, 1),
            "walter_cup_pct":   round(walter_cup_counts[tid] / n * 100, 1),
            "proj_pts_mean":    round(mean(all_pts), 1),
            "proj_pts_std":     round(stdev(all_pts), 1) if len(all_pts) > 1 else 0.0,
            "proj_pts_low":     sorted(all_pts)[int(n * 0.10)],
            "proj_pts_high":    sorted(all_pts)[int(n * 0.90)],
        }

    return results


# ── Validation (Season 2 backtest) ────────────────────────────────────────────

def run_validation(season_id: int = None, as_of_str: str = None, game_pct: float = None, verbose: bool = True):
    """
    Backtests the model using historical season data.
    Computes predicted standings at the midpoint (or as-of date) and compares
    to actual final standings. Prints Spearman rank correlation.

    season_id : DB season_id to validate (default: 2 for backward compat)
    as_of_str : YYYY-MM-DD snapshot date (default: midseason cutoff)
    verbose   : if False, suppresses all print output

    Returns {"spearman": float, "p_value": float} or None on failure.
    """
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from pwhl_btn.db.db_config import get_db_url
    from scipy.stats import spearmanr

    TARGET_SEASON = season_id if season_id is not None else 2
    engine  = create_engine(get_db_url())
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Get all games for the target season
        all_games = session.execute(text("""
            SELECT g.game_id, g.date,
                   g.home_team_id, g.away_team_id,
                   g.home_score,   g.away_score,
                   g.result_type,  g.game_status
            FROM games g
            WHERE g.season_id = :sid
            ORDER BY g.date ASC, g.game_id ASC
        """), {"sid": TARGET_SEASON}).fetchall()

        if not all_games:
            print(f"  ⚠️  No data found for season_id={TARGET_SEASON}")
            return

        # Split at midpoint or as-of date
        final_games = [g for g in all_games if g.game_status == 'final']

        if as_of_str:
            from datetime import datetime as _dt
            cutoff    = _dt.strptime(as_of_str, "%Y-%m-%d").date()
            played    = [g for g in final_games if g.date <= cutoff]
            remaining = [g for g in final_games if g.date >  cutoff]
            print(f"  Season {TARGET_SEASON}: {len(final_games)} total games | "
                  f"snapshot at {cutoff} ({len(played)} played, {len(remaining)} remaining)")
        elif game_pct is not None:
            split_idx = max(1, int(len(final_games) * game_pct))
            played    = final_games[:split_idx]
            remaining = final_games[split_idx:]
            snap_date = played[-1].date if played else "N/A"
            print(f"  Season {TARGET_SEASON}: {len(final_games)} total games | "
                  f"snapshot at {game_pct:.0%} (game {split_idx}, {snap_date})")
        else:
            midpoint_idx = len(final_games) // 2
            played       = final_games[:midpoint_idx]
            remaining    = final_games[midpoint_idx:]
            midpoint_date = played[-1].date if played else "N/A"
            print(f"  Season {TARGET_SEASON}: {len(final_games)} total games | "
                  f"midpoint at game {midpoint_idx} ({midpoint_date})")

        # Build current pts from first half
        team_ids = set()
        for g in played:
            team_ids.add(g.home_team_id)
            team_ids.add(g.away_team_id)

        current_pts = {tid: 0 for tid in team_ids}
        for g in played:
            h, a = g.home_team_id, g.away_team_id
            if g.home_score > g.away_score:
                current_pts[h] += 2
            else:
                current_pts[a] += 2
                if g.result_type in ('OT', 'SO'):
                    current_pts[h] += 1

        # Fetch team codes — try target season first, fall back to any season
        team_code_map = {}
        for row in session.execute(text(
            "SELECT team_id, team_code FROM teams ORDER BY season_id DESC"
        )).fetchall():
            if row.team_id not in team_code_map:  # first hit wins (most recent season)
                team_code_map[row.team_id] = row.team_code

        # Fetch goalie stats (SV%) for played games
        goalie_rows = session.execute(text("""
            SELECT ggs.team_id,
                   SUM(ggs.saves)         AS total_saves,
                   SUM(ggs.shots_against) AS total_sa
            FROM goalie_game_stats ggs
            JOIN games g ON g.game_id = ggs.game_id
            WHERE g.season_id   = :sid
              AND g.game_status = 'final'
              AND g.date       <= :cutoff
            GROUP BY ggs.team_id
        """), {"sid": TARGET_SEASON, "cutoff": played[-1].date if played else None}).fetchall()
        team_sv = {
            r.team_id: float(r.total_saves) / float(r.total_sa)
            if r.total_sa and float(r.total_sa) > 0 else 0.900
            for r in goalie_rows
        }

        # Fetch shots data for played games
        shot_rows = session.execute(text("""
            SELECT pgs.team_id,
                   SUM(pgs.shots) AS shots_for
            FROM player_game_stats pgs
            JOIN games g ON g.game_id = pgs.game_id
            WHERE g.season_id   = :sid
              AND g.game_status = 'final'
              AND g.date       <= :cutoff
            GROUP BY pgs.team_id
        """), {"sid": TARGET_SEASON, "cutoff": played[-1].date if played else None}).fetchall()
        team_shots_for = {r.team_id: int(r.shots_for or 0) for r in shot_rows}  # int() handles Decimal

        # Total shots against = sum of saves + goals against per team
        # (already have via goalie stats)
        team_shots_against = {
            r.team_id: int(r.total_sa or 0) for r in goalie_rows
        }

        # Build simple inputs from first half
        teams_simple = {}
        for tid in team_ids:
            tg = [g for g in played if g.home_team_id == tid or g.away_team_id == tid]
            gp = len(tg)
            pts = current_pts[tid]

            home_tg      = [g for g in tg if g.home_team_id == tid]
            home_wins    = sum(1 for g in home_tg if g.home_score > g.away_score)
            home_win_pct = home_wins / len(home_tg) if home_tg else 0.5

            # Goal differential — last 5 games
            last5_gd = 0
            for g in sorted(tg, key=lambda x: x.date, reverse=True)[:5]:
                last5_gd += (g.home_score - g.away_score) if g.home_team_id == tid                              else (g.away_score - g.home_score)

            # Recency-weighted points percentage (last 10 games weighted 2x)
            recent = sorted(tg, key=lambda x: x.date, reverse=True)[:10]
            recent_pts = 0
            for g in recent:
                h, a = g.home_team_id, g.away_team_id
                if g.home_score > g.away_score:
                    if h == tid: recent_pts += 2
                else:
                    if a == tid: recent_pts += 2
                    elif g.result_type in ('OT','SO'):
                        if h == tid: recent_pts += 1
            recent_pts_pct = recent_pts / (len(recent) * 2) if recent else 0.5
            blended_pts_pct = (pts / (gp * 2) * 0.5 + recent_pts_pct * 0.5) if gp else 0.5

            # Streak
            streak = 0
            for g in sorted(tg, key=lambda x: x.date, reverse=True):
                won = ((g.home_team_id == tid and g.home_score > g.away_score) or
                       (g.away_team_id == tid and g.away_score > g.home_score))
                if streak == 0:
                    streak = 1 if won else -1
                elif (streak > 0 and won) or (streak < 0 and not won):
                    streak += (1 if won else -1)
                else:
                    break

            ppg        = pts / gp if gp else 0.0
            rank_score = (streak * 3) + (ppg * 20) + (last5_gd * 1.5)

            # Shots ratio (proxy for possession/quality)
            sf = team_shots_for.get(tid, 0)
            sa = team_shots_against.get(tid, 0)
            shots_ratio = sf / (sf + sa) if (sf + sa) > 0 else 0.5

            # Team SV%
            sv_pct = team_sv.get(tid, 0.900)

            # PDO = SV% + shooting% (sum of luck metrics, mean-reverts to ~1.000)
            gf = sum(
                (g.home_score if g.home_team_id == tid else g.away_score)
                for g in tg
            )
            ga = sum(
                (g.away_score if g.home_team_id == tid else g.home_score)
                for g in tg
            )
            shots_taken = team_shots_for.get(tid, 1)
            sh_pct   = gf / shots_taken if shots_taken > 0 else 0.08
            pdo      = sv_pct + sh_pct

            PDO_MEAN = 1.000
            pdo_adj  = (PDO_MEAN - pdo) * 0.15
            adjusted_pts_pct = max(0.05, min(0.95, blended_pts_pct + pdo_adj))

            # xG proxy: shots_for * league_avg_sh_pct - shots_against * league_avg_sh_pct
            # Simplified: shots_ratio adjusted by SV% differential from league avg
            LEAGUE_AVG_SV = 0.920
            xg_ratio = (
                shots_ratio * (1 - LEAGUE_AVG_SV) /
                max((shots_ratio * (1 - LEAGUE_AVG_SV) +
                     (1 - shots_ratio) * (1 - sv_pct)), 0.001)
            )

            teams_simple[tid] = {
                "team_id":         tid,
                "team_code":       team_code_map.get(tid, str(tid)),
                "gp":              gp,
                "pts":             pts,
                "pts_pct":         adjusted_pts_pct,
                "raw_pts_pct":     pts / (gp * 2) if gp else 0.0,
                "home_win_pct":    home_win_pct,
                "last5_gd":        last5_gd,
                "rank_score":      rank_score,
                "shots_ratio":     shots_ratio,
                "sv_pct":          sv_pct,
                "pdo":             round(pdo, 3),
                "xg_ratio":        round(xg_ratio, 4),
                "games_remaining": len([g for g in remaining
                                        if g.home_team_id == tid or g.away_team_id == tid]),
            }

        # Simulate remaining Season 2 games
        strength = build_strength_map(teams_simple)
        remaining_dicts = [{
            "home_team_id": g.home_team_id,
            "away_team_id": g.away_team_id,
        } for g in remaining]

        rng = random.Random(42)
        playoff_counts    = defaultdict(int)
        pts_accumulator   = defaultdict(list)
        N = 10_000

        for _ in range(N):
            final_pts = simulate_once(remaining_dicts, current_pts, strength, rng)
            ranked    = sorted(final_pts.items(), key=lambda x: x[1], reverse=True)
            for rank, (tid, _) in enumerate(ranked):
                pts_accumulator[tid].append(final_pts[tid])
                if rank < 4:
                    playoff_counts[tid] += 1

        # Actual final standings from Season 2
        actual_pts = {tid: 0 for tid in team_ids}
        for g in final_games:
            h, a = g.home_team_id, g.away_team_id
            if g.home_score > g.away_score:
                actual_pts[h] += 2
            else:
                actual_pts[a] += 2
                if g.result_type in ('OT', 'SO'):
                    actual_pts[h] += 1

        # Compare predicted rank (by proj_pts_mean) vs actual rank
        pred_rank   = {tid: rank+1 for rank, (tid, _) in
                       enumerate(sorted(pts_accumulator.items(),
                                        key=lambda x: mean(x[1]), reverse=True))}
        actual_rank = {tid: rank+1 for rank, (tid, _) in
                       enumerate(sorted(actual_pts.items(), key=lambda x: x[1], reverse=True))}

        tids_sorted   = sorted(team_ids)
        pred_ranks    = [pred_rank[tid]   for tid in tids_sorted]
        actual_ranks  = [actual_rank[tid] for tid in tids_sorted]

        corr, pval = spearmanr(pred_ranks, actual_ranks)

        if verbose:
            print(f"\n  ── Season {TARGET_SEASON} Validation Results ──")
            print(f"  Spearman rank correlation: {corr:.3f}  (p={pval:.3f})")
            print(f"  (1.0 = perfect prediction, 0 = no correlation)\n")
            print(f"  {'Team':<8} {'Predicted':>10} {'Actual':>8} {'Pred Rank':>10} {'Act Rank':>9} {'SV%':>8} {'ShotRatio':>10} {'PDO':>7}")
            print(f"  {'-'*75}")
            for tid in tids_sorted:
                pm   = round(mean(pts_accumulator[tid]), 1)
                code = teams_simple[tid]["team_code"]
                sv   = teams_simple[tid].get("sv_pct", 0)
                sr   = teams_simple[tid].get("shots_ratio", 0)
                pdo  = teams_simple[tid].get("pdo", 0)
                print(f"  {code:<8} {pm:>10.1f} {actual_pts[tid]:>8} "
                      f"{pred_rank[tid]:>10} {actual_rank[tid]:>9} "
                      f"  {sv:>6.3f}   {sr:>8.3f}  {pdo:>6.3f}")

        return {
            "spearman": float(corr),
            "p_value":  float(pval),
            "teams": {
                team_code_map.get(tid, str(tid)): {
                    "pred_rank":   pred_rank[tid],
                    "actual_rank": actual_rank[tid],
                    "pred_pts":    round(mean(pts_accumulator[tid]), 1),
                    "actual_pts":  actual_pts[tid],
                }
                for tid in tids_sorted
            },
        }

    except ImportError:
        print("  scipy not installed — run: pip install scipy")
        return None
    finally:
        session.close()


# ── CLI ────────────────────────────────────────────────────────────────────────

def _print_results(results: dict):
    teams = sorted(results.values(), key=lambda x: x["playoff_pct"], reverse=True)
    print(f"\n  {'Team':<6} {'Pts':>4} {'Rem':>4} {'Playoff%':>9} {'WalterCup%':>11} "
          f"{'Proj Pts':>9} {'Range':>14}")
    print(f"  {'-'*65}")
    for t in teams:
        print(f"  {t['team_code']:<6} {t['current_pts']:>4} {t['games_remaining']:>4} "
              f"{t['playoff_pct']:>8.1f}% {t['walter_cup_pct']:>10.1f}% "
              f"{t['proj_pts_mean']:>9.1f} "
              f"  {t['proj_pts_low']}–{t['proj_pts_high']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n",        type=int, default=DEFAULT_N, help="Number of simulations")
    parser.add_argument("--validate", action="store_true",         help="Run Season 2 backtest")
    parser.add_argument("--season",   type=int, default=None,
                        help="season_id to validate (e.g. 5=S7 regular). Implies --validate.")
    parser.add_argument("--as-of",   type=str, default=None,
                        help="Snapshot date YYYY-MM-DD for validation (default: midseason)")
    parser.add_argument("--game-pct", type=float, default=None,
                        help="Snapshot at this fraction of season e.g. 0.33=1/3, 0.67=2/3")
    parser.add_argument("--export",   action="store_true",         help="Write JSON to output/")
    args = parser.parse_args()

    if args.validate or args.season:
        if args.season:
            print(f"\nRunning validation backtest for season_id={args.season}...")
            run_validation(season_id=args.season, as_of_str=args.as_of,
                           game_pct=args.game_pct)
        else:
            print("\nRunning Season 2 validation backtest...")
            run_validation()
    else:
        print(f"\nRunning PWHL playoff simulation ({args.n:,} runs)...")
        results = run_simulation(n=args.n)
        _print_results(results)

        if args.export:
            OUTPUT_DIR.mkdir(exist_ok=True)
            out_path = OUTPUT_DIR / "monte_carlo.json"
            with open(out_path, "w") as f:
                json.dump(results, f, indent=2)
            print(f"\n  Exported → {out_path}")



