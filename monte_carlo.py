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
import random
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db_queries import get_remaining_schedule, get_simulation_inputs

BASE_DIR    = Path(__file__).resolve().parent.parent
OUTPUT_DIR  = BASE_DIR / "output"
PLAYOFF_SPOTS = 4
DEFAULT_N     = 10_000


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
      35% — points percentage (season quality baseline)
      30% — power ranking score (current form: streak + ppg + last5_gd)
      20% — last 5 goal differential (recent momentum)
      15% — home win percentage
    """
    norm_pts_pct      = _normalize(teams, "pts_pct")
    norm_rank_score   = _normalize(teams, "rank_score")
    norm_last5_gd     = _normalize(teams, "last5_gd")
    norm_home_win_pct = _normalize(teams, "home_win_pct")

    strength = {}
    for tid in teams:
        strength[tid] = (
            0.35 * norm_pts_pct[tid]
          + 0.30 * norm_rank_score[tid]
          + 0.20 * norm_last5_gd[tid]
          + 0.15 * norm_home_win_pct[tid]
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

def simulate_once(
    remaining_games: list[dict],
    current_pts:     dict[int, int],
    strength:        dict[int, float],
    rng:             random.Random,
) -> dict[int, int]:
    """
    Simulates all remaining games once.
    Returns dict of team_id → final total points.
    OT/SO outcomes are simplified: loser gets 1 pt (50% chance per loss).
    """
    pts = dict(current_pts)  # copy so we don't mutate the original

    for game in remaining_games:
        h = game["home_team_id"]
        a = game["away_team_id"]

        if h not in strength or a not in strength:
            continue  # skip if team not in inputs (shouldn't happen)

        p_home_win = win_prob(h, a, strength)
        home_wins  = rng.random() < p_home_win

        if home_wins:
            pts[h] = pts.get(h, 0) + 2
            # Away team gets OTL point 30% of the time (approx PWHL OT rate)
            if rng.random() < 0.30:
                pts[a] = pts.get(a, 0) + 1
        else:
            pts[a] = pts.get(a, 0) + 2
            if rng.random() < 0.30:
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

def run_validation():
    """
    Backtests the model using Season 2 data.
    Computes predicted standings at the midpoint and compares to actual final standings.
    Prints Spearman rank correlation.

    Note: Vancouver and Seattle are excluded (expansion teams, no Season 2 data).
    """
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from db_queries import get_db_url
    from scipy.stats import spearmanr

    SEASON_2_ID = 2  # adjust if your season IDs differ
    engine  = create_engine(get_db_url())
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Get all Season 2 games
        all_games = session.execute(text("""
            SELECT g.game_id, g.date,
                   g.home_team_id, g.away_team_id,
                   g.home_score,   g.away_score,
                   g.result_type,  g.game_status
            FROM games g
            WHERE g.season_id = :sid
            ORDER BY g.date ASC, g.game_id ASC
        """), {"sid": SEASON_2_ID}).fetchall()

        if not all_games:
            print("  ⚠️  No Season 2 data found in DB")
            return

        # Split at midpoint
        final_games  = [g for g in all_games if g.game_status == 'final']
        midpoint_idx = len(final_games) // 2
        played       = final_games[:midpoint_idx]
        remaining    = final_games[midpoint_idx:]

        print(f"  Season 2: {len(final_games)} total games | "
              f"midpoint at game {midpoint_idx}")

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

        # Build simple inputs from first half for the 6 original teams
        teams_simple = {}
        for tid in team_ids:
            tg = [g for g in played if g.home_team_id == tid or g.away_team_id == tid]
            gp = len(tg)
            pts = current_pts[tid]

            home_tg    = [g for g in tg if g.home_team_id == tid]
            home_wins  = sum(1 for g in home_tg if g.home_score > g.away_score)
            home_win_pct = home_wins / len(home_tg) if home_tg else 0.5

            last5_gd = 0
            for g in sorted(tg, key=lambda x: x.date, reverse=True)[:5]:
                last5_gd += (g.home_score - g.away_score) if g.home_team_id == tid \
                             else (g.away_score - g.home_score)

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

            teams_simple[tid] = {
                "team_id":       tid,
                "team_code":     str(tid),
                "gp":            gp,
                "pts":           pts,
                "pts_pct":       pts / (gp * 2) if gp else 0.0,
                "home_win_pct":  home_win_pct,
                "last5_gd":      last5_gd,
                "rank_score":    rank_score,
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

        print(f"\n  ── Season 2 Validation Results ──")
        print(f"  Spearman rank correlation: {corr:.3f}  (p={pval:.3f})")
        print(f"  (1.0 = perfect prediction, 0 = no correlation)\n")
        print(f"  {'Team':<8} {'Predicted':>10} {'Actual':>8} {'Pred Rank':>10} {'Act Rank':>9}")
        print(f"  {'-'*50}")
        for tid in tids_sorted:
            pm = round(mean(pts_accumulator[tid]), 1)
            print(f"  {str(tid):<8} {pm:>10.1f} {actual_pts[tid]:>8} "
                  f"{pred_rank[tid]:>10} {actual_rank[tid]:>9}")

    except ImportError:
        print("  scipy not installed — run: pip install scipy")
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
    parser.add_argument("--export",   action="store_true",         help="Write JSON to output/")
    args = parser.parse_args()

    if args.validate:
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
