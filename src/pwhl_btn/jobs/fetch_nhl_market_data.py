"""
fetch_nhl_market_data.py — Fetch NHL market strength data for expansion candidates.

Hits the NHL records API for each candidate city, computes market strength
scores, and writes results into data/nhl/market_strength.json.

Attendance figures in that file are hardcoded from Hockey Reference and must
be updated manually — the NHL API does not expose per-team attendance.

Usage:
    python -m pwhl_btn.jobs.fetch_nhl_market_data
    python -m pwhl_btn.jobs.fetch_nhl_market_data --dry-run
"""

import argparse
import json
from datetime import date
from pathlib import Path

from pwhl_btn.nhl.market_strength import compute_market_scores

DATA_FILE = Path(__file__).resolve().parents[3] / "data" / "nhl" / "market_strength.json"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Print results without writing to file")
    args = parser.parse_args()

    print("\n── NHL Market Strength Data Fetch ──────────────────────────────")
    print("  Source: records.nhl.com/site/api/franchise-season-results")
    print("  Metrics: points%, home win%, playoff rate (last 3-5 seasons)")
    print("─" * 60)

    scores = compute_market_scores()

    # Load existing file to preserve hardcoded attendance data
    existing = json.loads(DATA_FILE.read_text(encoding="utf-8"))

    print(f"\n  Results:")
    print(f"  {'CITY':<12}  {'PTS%':>6}  {'HW%':>6}  {'PO RATE':>8}  {'SCORE':>7}")
    print(f"  {'─'*50}")

    for city, data in sorted(scores.items(), key=lambda x: -x[1]["market_strength_score"]):
        print(f"  {city:<12}  "
              f"{data['avg_pts_pct']:.3f}  "
              f"{data['avg_home_win']:.3f}  "
              f"{data['playoff_rate']:.2f}/1.00  "
              f"{data['market_strength_score']:>6.3f}/10")

        # Merge into existing file structure
        if city in existing["candidates"]:
            existing["candidates"][city]["api_derived"] = {
                "avg_pts_pct":           data["avg_pts_pct"],
                "avg_home_win_pct":      data["avg_home_win"],
                "playoff_rate":          data["playoff_rate"],
                "norm_pts_pct":          data["norm_pts_pct"],
                "norm_home_win":         data["norm_home_win"],
                "norm_playoff":          data["norm_playoff"],
                "market_strength_score": data["market_strength_score"],
                "seasons_used":          data["seasons_used"],
            }

    existing["_metadata"]["last_fetched"] = str(date.today())

    if args.dry_run:
        print("\n  [dry-run] Would write to:", DATA_FILE)
        print(json.dumps(existing, indent=2))
        return

    DATA_FILE.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    print(f"\n  Written to: {DATA_FILE}")
    print("  Attendance figures are hardcoded — update manually from Hockey Reference each season.")


if __name__ == "__main__":
    main()
