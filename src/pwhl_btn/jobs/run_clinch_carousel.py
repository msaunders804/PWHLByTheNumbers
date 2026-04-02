"""
run_clinch_carousel.py — Render the playoff clinch carousel for a team.

Produces 6 slides covering top scorers, dominant games, season record,
goalie stats, and a Claude-generated analysis blurb.

Usage:
    python -m pwhl_btn.jobs.run_clinch_carousel --team BOS
    python -m pwhl_btn.jobs.run_clinch_carousel --team BOS --skip-drive
    python -m pwhl_btn.jobs.run_clinch_carousel --team BOS --out-dir /tmp/output
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from pwhl_btn.db.db_queries import get_clinch_carousel_data
from pwhl_btn.render.clinch_render import render_clinch_carousel

OUTPUT_DIR = Path(__file__).resolve().parents[3] / "output"


def main():
    parser = argparse.ArgumentParser(description="PWHL Clinch Carousel Renderer")
    parser.add_argument("--team",       required=True,          help="Team code, e.g. BOS")
    parser.add_argument("--season",     type=int, default=8,    help="Season ID (default 8)")
    parser.add_argument("--out-dir",    default=None,           help="Output directory (default: output/)")
    parser.add_argument("--skip-drive", action="store_true",    help="Skip Google Drive upload")
    args = parser.parse_args()

    team_code = args.team.upper()
    out_dir   = Path(args.out_dir) if args.out_dir else OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n── Clinch Carousel · {team_code} · Season {args.season} ─────────────────")

    print("  Fetching season data from DB…")
    data = get_clinch_carousel_data(team_code, season_id=args.season)

    print(f"  {data['team_name']}  |  {data['record_str']}  |  {data['points']} pts  |  {data['win_pct']} W%")
    print(f"  Top scorer: {data['scorers'][0]['name']} ({data['scorers'][0]['points']} pts)" if data['scorers'] else "  No scorer data")
    print(f"  Goalie: {data['goalie']['name']} — {data['goalie']['shutouts']} SO, {data['goalie']['gaa']} GAA")

    print(f"\n  Rendering 6 slides…")
    outputs = render_clinch_carousel(data, out_dir=out_dir)

    if not args.skip_drive:
        _upload(outputs)

    print(f"\n✨ Done — {len(outputs)} slide(s) saved to {out_dir}")
    for p in outputs:
        print(f"   {p.name}")


def _upload(outputs: list[Path]):
    try:
        from pwhl_btn.integrations.google_drive import upload_files
        folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "")
        if folder_id:
            links = upload_files(outputs, folder_id)
            print(f"  Uploaded {len(links)} file(s) to Drive")
        else:
            print("  [Drive] GOOGLE_DRIVE_FOLDER_ID not set — skipping upload")
    except Exception as e:
        print(f"  [Drive] {e}")


if __name__ == "__main__":
    main()
