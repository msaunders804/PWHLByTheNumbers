"""
elo_baseline.py — Simple Elo rating baseline for PWHL standings prediction.

Builds per-team Elo ratings by replaying game results chronologically up to a
snapshot point, then projects final standings using expected-value math on the
remaining schedule.  Used as a naive baseline to benchmark against the Monte
Carlo model.

Elo parameters
--------------
  Initial rating  : 1500  (all teams equal at season start)
  K-factor        : 20    (update magnitude per game)
  Home advantage  : +100 Elo points added to home team before win-prob calc

Win probability
---------------
  P(home wins) = 1 / (1 + 10 ^ ((R_away - (R_home + HOME_ADV)) / 400))

Projection
----------
  For each remaining game the home team is credited
      E[pts_home] += P(home_win) * 2  +  P(OT) * 1
  where P(OT) is approximated from the historical league OT rate.
  The away team receives the symmetric complement.

  Predicted rank  → sort teams by projected total points (descending)
  Actual rank     → sort teams by actual end-of-season points (descending)
  Quality metric  → Spearman rank correlation between the two

Usage (CLI)
-----------
  PYTHONPATH=src python src/pwhl_btn/analytics/elo_baseline.py
  PYTHONPATH=src python src/pwhl_btn/analytics/elo_baseline.py --season 5 --game-pct 0.33
  PYTHONPATH=src python src/pwhl_btn/analytics/elo_baseline.py --season 5 --game-pct 0.67
"""

import argparse
from datetime import datetime as _dt
from statistics import mean

from scipy.stats import spearmanr
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from pwhl_btn.db.db_config import get_db_url

# ── Elo constants ──────────────────────────────────────────────────────────────

INITIAL_RATING = 1500
K_FACTOR       = 20
HOME_ADV       = 100     # Elo points added to home team expected score

# Approximate fraction of PWHL games that go to OT/SO.
# When regulation ends in a tie each team earns ~1 pt on average.
# This is used to scale the "tie" probability into expected points.
PWHL_OT_RATE   = 0.20    # ~20% of games reach OT (calibrate from data if desired)


# ── Core Elo math ──────────────────────────────────────────────────────────────

def _expected(rating_a: float, rating_b: float) -> float:
    """P(A beats B) under standard Elo formula."""
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400))


def _update(rating: float, expected: float, actual: float) -> float:
    """Return updated rating after one game.  actual is 1 (win), 0 (loss), or 0.5 (OT)."""
    return rating + K_FACTOR * (actual - expected)


def build_elo_ratings(played_games: list) -> dict[int, float]:
    """
    Replay played_games in chronological order and return the final Elo ratings.

    Each element of played_games must have:
        .home_team_id, .away_team_id, .home_score, .away_score, .result_type

    OT/SO results are treated as 0.5 wins for the loser (split Elo credit)
    so the rating reflects quality rather than luck in the shootout.
    """
    ratings: dict[int, float] = {}

    for g in sorted(played_games, key=lambda x: (x.date, x.game_id)):
        h = g.home_team_id
        a = g.away_team_id

        r_h = ratings.get(h, INITIAL_RATING)
        r_a = ratings.get(a, INITIAL_RATING)

        # Home-advantage adjusted expected scores
        e_h = _expected(r_h + HOME_ADV, r_a)
        e_a = 1.0 - e_h

        if g.home_score > g.away_score:
            # Regulation or OT/SO win for home
            s_h, s_a = (1.0, 0.0) if g.result_type == "REG" else (0.75, 0.25)
        else:
            # Away win
            s_h, s_a = (0.0, 1.0) if g.result_type == "REG" else (0.25, 0.75)

        ratings[h] = _update(r_h, e_h, s_h)
        ratings[a] = _update(r_a, e_a, s_a)

    return ratings


def project_points(
    remaining_games: list,
    current_pts:     dict[int, int],
    ratings:         dict[int, float],
) -> dict[int, float]:
    """
    Deterministically project final point totals using Elo win probabilities.

    For each remaining game:
        P_reg_win  = P(win) * (1 - PWHL_OT_RATE)      → winner gets 2 pts
        P_ot       = PWHL_OT_RATE                      → winner gets 2, loser 1
        P_reg_loss = (1 - P(win)) * (1 - PWHL_OT_RATE)

    Expected points added per team per game:
        home: P_reg_win * 2  +  P_ot * (P_home_wins_ot * 2 + (1-P_home_wins_ot) * 1)
            ≈ P_reg_win * 2  +  P_ot * (P_h_ot * 2 + (1-P_h_ot) * 1)
            where P_h_ot = 0.5 (coin-flip in OT, consistent with Monte Carlo)
        away: symmetric complement

    Simplifies to:
        E[pts_home] += p_h * 2  +  PWHL_OT_RATE * 0.5
        E[pts_away] += p_a * 2  +  PWHL_OT_RATE * 0.5
        where p_h, p_a are the regulation win probabilities (renormalised to sum to 1
        after removing the OT-rate mass).
    """
    proj = {tid: float(pts) for tid, pts in current_pts.items()}

    for g in remaining_games:
        h = g.home_team_id if hasattr(g, "home_team_id") else g["home_team_id"]
        a = g.away_team_id if hasattr(g, "away_team_id") else g["away_team_id"]

        if h not in ratings or a not in ratings:
            continue

        r_h = ratings.get(h, INITIAL_RATING)
        r_a = ratings.get(a, INITIAL_RATING)

        # Win probability going into regulation
        p_h = _expected(r_h + HOME_ADV, r_a)
        p_a = 1.0 - p_h

        reg_rate = 1.0 - PWHL_OT_RATE

        # Expected points: reg win/loss + OT (50/50 winner, loser gets 1)
        e_pts_h = (p_h * reg_rate * 2) + (PWHL_OT_RATE * (0.5 * 2 + 0.5 * 1))
        e_pts_a = (p_a * reg_rate * 2) + (PWHL_OT_RATE * (0.5 * 2 + 0.5 * 1))

        proj[h] = proj.get(h, 0.0) + e_pts_h
        proj[a] = proj.get(a, 0.0) + e_pts_a

    return proj


# ── Validation (mirrors run_validation interface) ──────────────────────────────

def run_elo_validation(
    season_id: int   = None,
    game_pct:  float = None,
    as_of_str: str   = None,
    verbose:   bool  = True,
) -> dict | None:
    """
    Backtests the Elo baseline against a completed season.

    Parameters match run_validation() in monte_carlo.py so the two can be
    called side-by-side in comparison scripts.

    Returns
    -------
    {
        "spearman": float,
        "p_value":  float,
        "teams": {
            team_code: {
                "pred_rank":   int,
                "actual_rank": int,
                "pred_pts":    float,
                "actual_pts":  int,
                "elo_rating":  float,
            }
        }
    }
    """
    TARGET_SEASON = season_id if season_id is not None else 2

    engine  = create_engine(get_db_url())
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # ── Load all games for the target season ──────────────────────────────
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
            print(f"  No data for season_id={TARGET_SEASON}")
            return None

        final_games = [g for g in all_games if g.game_status == "final"]

        # ── Determine snapshot split ──────────────────────────────────────────
        if as_of_str:
            cutoff    = _dt.strptime(as_of_str, "%Y-%m-%d").date()
            played    = [g for g in final_games if g.date <= cutoff]
            remaining = [g for g in final_games if g.date >  cutoff]
            snap_label = f"as-of {cutoff}"
        elif game_pct is not None:
            split_idx = max(1, int(len(final_games) * game_pct))
            played    = final_games[:split_idx]
            remaining = final_games[split_idx:]
            snap_label = f"{game_pct:.0%} of season (game {split_idx})"
        else:
            mid       = len(final_games) // 2
            played    = final_games[:mid]
            remaining = final_games[mid:]
            snap_label = f"midpoint (game {mid})"

        if verbose:
            print(f"  Season {TARGET_SEASON}: {len(final_games)} games | "
                  f"snapshot at {snap_label} | "
                  f"{len(played)} played, {len(remaining)} remaining")

        # ── Team IDs and codes ────────────────────────────────────────────────
        team_ids = {g.home_team_id for g in played} | {g.away_team_id for g in played}

        team_code_map: dict[int, str] = {}
        for row in session.execute(text(
            "SELECT team_id, team_code FROM teams ORDER BY season_id DESC"
        )).fetchall():
            if row.team_id not in team_code_map:
                team_code_map[row.team_id] = row.team_code

        # ── Build current point totals from played games ──────────────────────
        current_pts: dict[int, int] = {tid: 0 for tid in team_ids}
        for g in played:
            h, a = g.home_team_id, g.away_team_id
            if g.home_score > g.away_score:
                current_pts[h] += 2
            else:
                current_pts[a] += 2
                if g.result_type in ("OT", "SO"):
                    current_pts[h] += 1

        # ── Build Elo ratings from played games ───────────────────────────────
        ratings = build_elo_ratings(played)

        # Ensure every team has a rating (teams with no games yet get 1500)
        for tid in team_ids:
            ratings.setdefault(tid, INITIAL_RATING)

        # ── Project remaining games ───────────────────────────────────────────
        proj_pts = project_points(remaining, current_pts, ratings)

        # ── Actual final standings ────────────────────────────────────────────
        actual_pts: dict[int, int] = {tid: 0 for tid in team_ids}
        for g in final_games:
            h, a = g.home_team_id, g.away_team_id
            if g.home_score > g.away_score:
                actual_pts[h] += 2
            else:
                actual_pts[a] += 2
                if g.result_type in ("OT", "SO"):
                    actual_pts[h] += 1

        # ── Rank comparison ───────────────────────────────────────────────────
        tids_sorted = sorted(team_ids)

        pred_rank = {
            tid: rank + 1
            for rank, (tid, _) in enumerate(
                sorted(proj_pts.items(), key=lambda x: x[1], reverse=True)
            )
        }
        actual_rank = {
            tid: rank + 1
            for rank, (tid, _) in enumerate(
                sorted(actual_pts.items(), key=lambda x: x[1], reverse=True)
            )
        }

        pred_ranks   = [pred_rank[tid]   for tid in tids_sorted]
        actual_ranks = [actual_rank[tid] for tid in tids_sorted]

        corr, pval = spearmanr(pred_ranks, actual_ranks)

        if verbose:
            print(f"\n  ── Elo Baseline: Season {TARGET_SEASON} Validation ──")
            print(f"  Spearman rank correlation : {corr:.3f}  (p={pval:.3f})")
            print(f"  (1.0 = perfect prediction, 0 = no correlation)\n")
            print(f"  {'Team':<8} {'Elo':>7} {'Cur Pts':>8} {'Proj Pts':>9} "
                  f"{'Actual Pts':>11} {'Pred Rank':>10} {'Act Rank':>9}")
            print(f"  {'-'*68}")
            for tid in sorted(tids_sorted, key=lambda t: pred_rank[t]):
                code = team_code_map.get(tid, str(tid))
                print(f"  {code:<8} {ratings[tid]:>7.1f} {current_pts[tid]:>8} "
                      f"{proj_pts[tid]:>9.1f} {actual_pts[tid]:>11} "
                      f"{pred_rank[tid]:>10} {actual_rank[tid]:>9}")

        return {
            "spearman": float(corr),
            "p_value":  float(pval),
            "teams": {
                team_code_map.get(tid, str(tid)): {
                    "pred_rank":   pred_rank[tid],
                    "actual_rank": actual_rank[tid],
                    "pred_pts":    round(proj_pts[tid], 1),
                    "actual_pts":  actual_pts[tid],
                    "elo_rating":  round(ratings[tid], 1),
                }
                for tid in tids_sorted
            },
        }

    finally:
        session.close()


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Elo baseline standings predictor — PWHL By The Numbers"
    )
    parser.add_argument("--season",   type=int,   default=5,
                        help="season_id to validate (default: 5 = Season 7)")
    parser.add_argument("--game-pct", type=float, default=None,
                        help="Snapshot fraction e.g. 0.33, 0.67, 0.90")
    parser.add_argument("--as-of",   type=str,   default=None,
                        help="Snapshot date YYYY-MM-DD")
    args = parser.parse_args()

    print(f"\nRunning Elo baseline validation (season_id={args.season})...")
    result = run_elo_validation(
        season_id=args.season,
        game_pct=args.game_pct,
        as_of_str=args.as_of,
        verbose=True,
    )
    if result:
        print(f"\n  Final: rho={result['spearman']:.3f}  p={result['p_value']:.3f}")
