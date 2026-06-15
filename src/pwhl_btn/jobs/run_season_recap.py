"""
run_season_recap.py — Generates 4-slide season recap carousels for all 8 PWHL teams.

Each team gets:
  slide 1 — Hook: team name + "2025-26 Season Recap" + record
  slide 2 — Offense: shots, goals, goal leader, points leader
  slide 3 — Defence: shots against, shutouts, SV%, top goalie
  slide 4 — Fun: home/away wins, OT wins, PIM, plus/minus leader

Usage:
  python -m pwhl_btn.jobs.run_season_recap
  python -m pwhl_btn.jobs.run_season_recap --team BOS
  python -m pwhl_btn.jobs.run_season_recap --team MIN --team MTL
"""
from __future__ import annotations

import argparse
from pathlib import Path

from pwhl_btn.db.db_queries import (
    get_all_season_teams,
    get_season_recap_data,
    TEAM_CODE_MAP,
)
from pwhl_btn.render.season_recap_render import render_all_slides

SEASON_ID  = 8
OUTPUT_DIR = Path(__file__).resolve().parents[3] / "src" / "pwhl_btn" / "render" / "output"

ALL_TEAM_CODES = list(TEAM_CODE_MAP.keys())


def run(team_codes: list[str] | None = None, out_dir: Path | None = None) -> None:
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    codes   = team_codes or ALL_TEAM_CODES

    print(f"\n=== PWHL 2025-26 Season Recap ({len(codes)} team(s)) ===")

    for code in codes:
        print(f"\n--- {code} ---")
        data = get_season_recap_data(code, SEASON_ID)
        if not data:
            print(f"  [skip] no data found for {code}")
            continue

        print(f"  {data['team_name']}  |  {data['record_str']}  |  {data['points']} PTS")
        paths = render_all_slides(data, out_dir)
        print(f"  {len(paths)} slides rendered")

    print(f"\nDone. Output: {out_dir}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Render PWHL season recap slides")
    parser.add_argument(
        "--team", action="append", dest="teams", metavar="CODE",
        help="Team code(s) to render (e.g. --team BOS --team MIN). Default: all 8.",
    )
    args = parser.parse_args()
    run(team_codes=[t.upper() for t in args.teams] if args.teams else None)
