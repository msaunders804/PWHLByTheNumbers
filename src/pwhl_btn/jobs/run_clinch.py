"""
run_clinch.py — Check for clinched/eliminated teams and render announcement slides.

Computes which PWHL teams have mathematically clinched a playoff spot or been
eliminated, then generates a clinch announcement slide for each clinched team.

Usage:
    python -m pwhl_btn.jobs.run_clinch                  # check all teams, render clinched
    python -m pwhl_btn.jobs.run_clinch --team-id 4      # force render for team 4
    python -m pwhl_btn.jobs.run_clinch --dry-run         # print status, no rendering
"""
from __future__ import annotations

import argparse
from pathlib import Path

from pwhl_btn.analytics.clinch import check_clinched, check_eliminated, PLAYOFF_SPOTS
from pwhl_btn.db.db_queries import get_clinch_data, get_clinch_slide_data
from pwhl_btn.render.clinch_render import render_clinch_slide

OUTPUT_DIR = Path(__file__).resolve().parents[3] / "render" / "output"
SEASON_ID  = 8


def run(team_id: int | None = None, dry_run: bool = False) -> list[Path]:
    """
    Check clinch/elimination status and render slides for clinched teams.

    Args:
        team_id:  If set, force-render this specific team (skip clinch check).
        dry_run:  Print status without rendering.

    Returns:
        List of paths to generated PNG files.
    """
    print(f"\n── Playoff Clinch / Elimination Check · Season {SEASON_ID} ──────────")

    teams      = get_clinch_data(SEASON_ID)
    clinched   = check_clinched(teams, playoff_spots=PLAYOFF_SPOTS)
    eliminated = check_eliminated(teams, playoff_spots=PLAYOFF_SPOTS)

    # Summary table
    print(f"\n  {'Team':<8} {'PTS':>4}  {'MAX':>4}  {'REM':>4}  {'Status'}")
    print(f"  {'─'*8} {'─'*4}  {'─'*4}  {'─'*4}  {'─'*12}")
    for tid, info in sorted(teams.items(), key=lambda x: -x[1]["pts"]):
        max_pts = info["pts"] + info["games_remaining"] * 3
        if clinched[tid]:
            status = "✅ CLINCHED"
        elif eliminated[tid]:
            status = "❌ ELIMINATED"
        else:
            status = "   in play"
        print(f"  {info['team_code']:<8} {info['pts']:>4}  {max_pts:>4}  {info['games_remaining']:>4}  {status}")

    clinched_ids   = [tid for tid, v in clinched.items() if v]
    eliminated_ids = [tid for tid, v in eliminated.items() if v]
    print(f"\n  Clinched: {len(clinched_ids)} / {len(teams)}   Eliminated: {len(eliminated_ids)} / {len(teams)}")

    if dry_run:
        print("\n  [dry-run] No slides rendered.")
        return []

    # Determine which teams to render for
    if team_id is not None:
        render_ids = [team_id]
        print(f"\n  Forcing render for team_id={team_id}")
    else:
        render_ids = clinched_ids

    if not render_ids:
        print("\n  No clinched teams — nothing to render.")
        return []

    out_dir = Path(__file__).resolve().parents[3] / "render" / "output"
    out_dir.mkdir(parents=True, exist_ok=True)

    outputs = []
    print(f"\n🎬 Rendering {len(render_ids)} clinch slide(s)...")
    for tid in render_ids:
        team_code = teams.get(tid, {}).get("team_code", str(tid))
        print(f"  → {team_code} (team_id={tid})")
        try:
            data = get_clinch_slide_data(tid, SEASON_ID)
            path = render_clinch_slide(data, out_dir=out_dir)
            outputs.append(path)
        except Exception as e:
            print(f"    ERROR: {e}")

    print(f"\n✨ Done — {len(outputs)} slide(s) saved to {out_dir}")
    return outputs


def main():
    parser = argparse.ArgumentParser(description="PWHL Clinch / Elimination Checker & Slide Renderer")
    parser.add_argument("--team-id", type=int, default=None,
                        help="Force render for a specific team_id")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print clinch/elimination status without rendering slides")
    args = parser.parse_args()

    run(team_id=args.team_id, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
