"""
run_eliminated.py — Render the playoff elimination announcement and Gold Plan slides.

Produces three 1080×1920 PNGs:
  1. eliminated_{TEAM}.png      — ELIMINATED announcement card
  2. gold_plan_standings.png    — Gold Plan standings table (slide 2)
  3. gold_plan_rules.png        — Gold Plan rules + PWHL vs. other leagues (slide 3)

Elimination date, games remaining, and Gold Plan points are all derived
automatically from the database — no hardcoded stats needed.

Usage:
    python -m pwhl_btn.jobs.run_eliminated            # VAN (default)
    python -m pwhl_btn.jobs.run_eliminated --team SEA
    python -m pwhl_btn.jobs.run_eliminated --gold-plan-only
"""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from pwhl_btn.db.db_queries import (
    get_elimination_slide_data,
    get_auto_gold_plan_data,
    find_elimination_date,
)
from pwhl_btn.render.eliminated_render import (
    render_eliminated_announcement,
    render_gold_plan_standings,
    render_gold_plan_rules,
)

OUTPUT_DIR = Path(__file__).resolve().parents[3] / "render" / "output"

_DEFAULT_TEAM = "VAN"


def run(team_code: str = _DEFAULT_TEAM,
        gold_plan_only: bool = False,
        dry_run: bool = False) -> list[Path]:

    # Derive elimination date from DB
    elim_date_obj, games_rem = find_elimination_date(team_code)
    elim_date_str = elim_date_obj.strftime("%B %d, %Y").replace(" 0", " ") if elim_date_obj else "TBD"

    print(f"\n-- Elimination / Gold Plan Renderer - Season 8 ---------------------")
    print(f"   Team: {team_code}   Elim date: {elim_date_str}   Games remaining: {games_rem}")
    print(f"   Output -> {OUTPUT_DIR}\n")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []

    if dry_run:
        print("  [dry-run] No slides rendered.")
        return outputs

    # -- Slide 1: Elimination announcement ------------------------------------
    if not gold_plan_only:
        print("  -> Rendering elimination announcement...")
        elim_data = get_elimination_slide_data(team_code, elim_date_str)
        path = render_eliminated_announcement(elim_data, out_dir=OUTPUT_DIR)
        outputs.append(path)

    # -- Slide 2: Gold Plan standings -----------------------------------------
    print("  -> Rendering Gold Plan standings slide...")
    gp_data = get_auto_gold_plan_data()
    path = render_gold_plan_standings(gp_data, out_dir=OUTPUT_DIR)
    outputs.append(path)

    # -- Slide 3: Gold Plan rules explainer -----------------------------------
    print("  -> Rendering Gold Plan rules slide...")
    path = render_gold_plan_rules(out_dir=OUTPUT_DIR)
    outputs.append(path)

    print(f"\nDone -- {len(outputs)} slide(s) saved to {OUTPUT_DIR}")
    return outputs


def main():
    parser = argparse.ArgumentParser(description="PWHL Elimination & Gold Plan Slide Renderer")
    parser.add_argument("--team",           default=_DEFAULT_TEAM, help="Team code (default: VAN)")
    parser.add_argument("--gold-plan-only", action="store_true",   help="Skip elimination announcement, render only Gold Plan slides")
    parser.add_argument("--dry-run",        action="store_true",   help="Print config without rendering")
    args = parser.parse_args()

    run(
        team_code=args.team,
        gold_plan_only=args.gold_plan_only,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
