"""
derive_weights.py — Derives Monte Carlo strength model weights via Multiple
Linear Regression on Season 7 (season_id=5) data.

Methodology:
  - Uses first half of Season 7 as training features
  - Target variable is final season points (second half outcomes)
  - Features: pts_pct, rank_score, last5_gd, home_win_pct, sv_pct, shots_ratio, xg_ratio
  - Outputs normalized weights summing to 1.0 for use in build_strength_map()

Usage:
    python derive_weights.py            # run regression, print weights
    python derive_weights.py --save     # also save weights to weights.json
    python derive_weights.py --all-pcts # test multiple snapshot points
"""

import argparse
import json
import sys
from pathlib import Path
from collections import defaultdict

from pwhl_btn.db.db_config import get_db_url
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

try:
    import numpy as np
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import r2_score
except ImportError:
    print("Missing dependencies. Run:")
    print("  pip install numpy scikit-learn")
    sys.exit(1)

TRAIN_SEASON = 5   # S7 regular season
LEAGUE_AVG_SV = 0.920

engine  = create_engine(get_db_url())
Session = sessionmaker(bind=engine)


# ── Feature extraction ─────────────────────────────────────────────────────────

def get_team_features_at_snapshot(session, season_id: int,
                                   game_pct: float) -> dict[int, dict]:
    """
    Builds feature vector for each team using only games up to the snapshot point.
    Returns dict of team_id → feature dict.
    """
    all_games = session.execute(text("""
        SELECT g.game_id, g.date, g.home_team_id, g.away_team_id,
               g.home_score, g.away_score, g.result_type, g.game_status
        FROM games g
        WHERE g.season_id = :sid AND g.game_status = 'final'
        ORDER BY g.date ASC, g.game_id ASC
    """), {"sid": season_id}).fetchall()

    if not all_games:
        return {}

    split_idx = max(1, int(len(all_games) * game_pct))
    played    = all_games[:split_idx]
    cutoff    = played[-1].date

    team_ids = set()
    for g in played:
        team_ids.add(g.home_team_id)
        team_ids.add(g.away_team_id)

    # Points from played games
    current_pts = defaultdict(int)
    for g in played:
        h, a = g.home_team_id, g.away_team_id
        if g.home_score > g.away_score:
            current_pts[h] += 2
        else:
            current_pts[a] += 2
            if g.result_type in ('OT', 'SO'):
                current_pts[h] += 1

    # Goalie SV%
    goalie_rows = session.execute(text("""
        SELECT ggs.team_id,
               SUM(ggs.saves)         AS total_saves,
               SUM(ggs.shots_against) AS total_sa
        FROM goalie_game_stats ggs
        JOIN games g ON g.game_id = ggs.game_id
        WHERE g.season_id = :sid AND g.game_status = 'final'
          AND g.date <= :cutoff
        GROUP BY ggs.team_id
    """), {"sid": season_id, "cutoff": cutoff}).fetchall()
    team_sv = {
        r.team_id: float(r.total_saves) / float(r.total_sa)
        if r.total_sa and float(r.total_sa) > 0 else 0.900
        for r in goalie_rows
    }

    # Shots for/against
    shot_rows = session.execute(text("""
        SELECT pgs.team_id, SUM(pgs.shots) AS shots_for
        FROM player_game_stats pgs
        JOIN games g ON g.game_id = pgs.game_id
        WHERE g.season_id = :sid AND g.game_status = 'final'
          AND g.date <= :cutoff
        GROUP BY pgs.team_id
    """), {"sid": season_id, "cutoff": cutoff}).fetchall()
    team_shots_for = {r.team_id: int(r.shots_for or 0) for r in shot_rows}
    team_shots_against = {r.team_id: int(r.total_sa or 0) for r in goalie_rows}

    features = {}
    for tid in team_ids:
        tg = [g for g in played if g.home_team_id == tid or g.away_team_id == tid]
        gp  = len(tg)
        pts = current_pts[tid]
        if gp == 0:
            continue

        # Home win pct
        home_tg      = [g for g in tg if g.home_team_id == tid]
        home_wins    = sum(1 for g in home_tg if g.home_score > g.away_score)
        home_win_pct = home_wins / len(home_tg) if home_tg else 0.5

        # Last 5 goal differential
        last5_gd = 0
        for g in sorted(tg, key=lambda x: x.date, reverse=True)[:5]:
            last5_gd += (g.home_score - g.away_score) if g.home_team_id == tid \
                         else (g.away_score - g.home_score)

        # Recency-weighted pts_pct
        recent = sorted(tg, key=lambda x: x.date, reverse=True)[:10]
        recent_pts = 0
        for g in recent:
            h, a = g.home_team_id, g.away_team_id
            if g.home_score > g.away_score:
                if h == tid: recent_pts += 2
            else:
                if a == tid: recent_pts += 2
                elif g.result_type in ('OT', 'SO'):
                    if h == tid: recent_pts += 1
        recent_pts_pct = recent_pts / (len(recent) * 2) if recent else 0.5
        blended_pts_pct = pts / (gp * 2) * 0.5 + recent_pts_pct * 0.5

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

        ppg        = pts / gp
        rank_score = (streak * 3) + (ppg * 20) + (last5_gd * 1.5)

        # Shots ratio + xG proxy
        sf = team_shots_for.get(tid, 0)
        sa = team_shots_against.get(tid, 0)
        shots_ratio = sf / (sf + sa) if (sf + sa) > 0 else 0.5
        sv_pct      = team_sv.get(tid, 0.900)

        gf = sum((g.home_score if g.home_team_id == tid else g.away_score) for g in tg)
        sh_pct  = gf / sf if sf > 0 else 0.08
        pdo     = sv_pct + sh_pct
        PDO_MEAN = 1.000
        pdo_adj  = (PDO_MEAN - pdo) * 0.15
        adjusted_pts_pct = max(0.05, min(0.95, blended_pts_pct + pdo_adj))

        xg_ratio = (
            shots_ratio * (1 - LEAGUE_AVG_SV) /
            max((shots_ratio * (1 - LEAGUE_AVG_SV) +
                 (1 - shots_ratio) * (1 - sv_pct)), 0.001)
        )

        features[tid] = {
            "pts_pct":      adjusted_pts_pct,
            "rank_score":   rank_score,
            "last5_gd":     last5_gd,
            "home_win_pct": home_win_pct,
            "sv_pct":       sv_pct,
            "shots_ratio":  shots_ratio,
            "xg_ratio":     xg_ratio,
            "gp":           gp,
            "pts":          pts,
        }

    return features


def get_final_pts(session, season_id: int) -> dict[int, int]:
    """Returns actual final points for all teams in the season."""
    all_games = session.execute(text("""
        SELECT g.home_team_id, g.away_team_id,
               g.home_score, g.away_score, g.result_type
        FROM games g
        WHERE g.season_id = :sid AND g.game_status = 'final'
    """), {"sid": season_id}).fetchall()

    pts = defaultdict(int)
    for g in all_games:
        h, a = g.home_team_id, g.away_team_id
        if g.home_score > g.away_score:
            pts[h] += 2
        else:
            pts[a] += 2
            if g.result_type in ('OT', 'SO'):
                pts[h] += 1
    return dict(pts)


# ── Regression ─────────────────────────────────────────────────────────────────

FEATURE_NAMES = [
    "pts_pct", "rank_score", "last5_gd",
    "home_win_pct", "sv_pct", "shots_ratio", "xg_ratio"
]


def run_regression(game_pct: float = 0.50, verbose: bool = True) -> dict:
    """
    Trains Ridge regression on team features at snapshot, target = final pts.
    Returns dict of feature → normalized weight.
    """
    session = Session()
    try:
        features  = get_team_features_at_snapshot(session, TRAIN_SEASON, game_pct)
        final_pts = get_final_pts(session, TRAIN_SEASON)
    finally:
        session.close()

    if len(features) < 4:
        raise ValueError(f"Not enough teams ({len(features)}) for regression")

    tids = sorted(features.keys())
    X = np.array([[features[tid][f] for f in FEATURE_NAMES] for tid in tids])
    y = np.array([final_pts.get(tid, 0) for tid in tids], dtype=float)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Ridge regression — regularization prevents overfitting on 6 teams
    model = Ridge(alpha=1.0)
    model.fit(X_scaled, y)

    y_pred = model.predict(X_scaled)
    r2     = r2_score(y, y_pred)

    raw_coefs = model.coef_
    # Keep only positive coefficients (negative = feature hurts prediction)
    # and normalize to sum to 1.0
    pos_coefs = np.maximum(raw_coefs, 0)
    total     = pos_coefs.sum()
    if total == 0:
        # Fallback: equal weights if all negative
        weights = {f: round(1/len(FEATURE_NAMES), 4) for f in FEATURE_NAMES}
    else:
        weights = {f: round(float(pos_coefs[i] / total), 4)
                   for i, f in enumerate(FEATURE_NAMES)}

    if verbose:
        print(f"\n  ── Regression Results (snapshot={game_pct:.0%}, season_id={TRAIN_SEASON}) ──")
        print(f"  R² = {r2:.3f}  (1.0 = perfect fit, with {len(tids)} teams)")
        print(f"\n  Raw coefficients (before normalization):")
        for f, c in zip(FEATURE_NAMES, raw_coefs):
            bar = "█" * int(abs(c) * 5) if abs(c) > 0.1 else ""
            sign = "+" if c >= 0 else "-"
            print(f"    {f:<16} {sign}{abs(c):>6.3f}  {bar}")
        print(f"\n  Normalized weights (for build_strength_map):")
        for f, w in sorted(weights.items(), key=lambda x: x[1], reverse=True):
            bar = "█" * int(w * 40)
            print(f"    {f:<16} {w:.4f}  {bar}")
        print(f"\n  Predicted vs Actual:")
        for tid, yp, ya in zip(tids, y_pred, y):
            print(f"    team_id={tid}  predicted={yp:.1f}  actual={ya:.0f}")

    return weights


def run_all_snapshots():
    """Tests regression at multiple snapshot points to show model accuracy curve."""
    print("\n  ── Regression Weights vs Snapshot Point ──")
    print(f"  {'Snapshot':<10} {'pts_pct':>8} {'rank_sc':>8} {'last5':>7} "
          f"{'home%':>7} {'sv_pct':>7} {'shots':>7} {'xg':>7}")
    print(f"  {'-'*65}")

    for pct in [0.33, 0.50, 0.67, 0.80]:
        try:
            w = run_regression(game_pct=pct, verbose=False)
            print(f"  {pct:.0%}        "
                  f"{w.get('pts_pct',0):>8.3f} "
                  f"{w.get('rank_score',0):>8.3f} "
                  f"{w.get('last5_gd',0):>7.3f} "
                  f"{w.get('home_win_pct',0):>7.3f} "
                  f"{w.get('sv_pct',0):>7.3f} "
                  f"{w.get('shots_ratio',0):>7.3f} "
                  f"{w.get('xg_ratio',0):>7.3f}")
        except Exception as e:
            print(f"  {pct:.0%}        ERROR: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-pct", type=float, default=0.50,
                        help="Snapshot fraction for regression (default: 0.50)")
    parser.add_argument("--save",     action="store_true",
                        help="Save derived weights to weights.json")
    parser.add_argument("--all-pcts", action="store_true",
                        help="Run regression at 33%%, 50%%, 67%%, 80%% snapshots")
    args = parser.parse_args()

    if args.all_pcts:
        run_all_snapshots()
    else:
        weights = run_regression(game_pct=args.game_pct)
        if args.save:
            out = Path(__file__).resolve().parent / "weights.json"
            with open(out, "w") as f:
                json.dump({"weights": weights, "game_pct": args.game_pct,
                           "season_id": TRAIN_SEASON}, f, indent=2)
            print(f"\n  Saved → {out}")
