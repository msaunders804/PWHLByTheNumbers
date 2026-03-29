"""
run_daily_records.py — Nightly check for record-breaking events and milestones.

Detects from games played in the last day:
  - Goal differential records (new season best)
  - Most skaters with a point — single team (new season best)
  - Season points leader record (new season high for individual)
  - Game attendance record (new season best)
  - Hat tricks (any 3+ goal game by a player)
  - First career PWHL goals
  - Longest player point streak (new season best)
  - Longest goalie shutout streak (new season best)

Renders slides using the record_breaking template and uploads to Google Drive.

Usage:
    python -m pwhl_btn.jobs.run_daily_records          # check last 1 day (default)
    python -m pwhl_btn.jobs.run_daily_records --days 2 # wider window (catch missed games)
    python -m pwhl_btn.jobs.run_daily_records --dry-run # detect only, no render/upload
    python -m pwhl_btn.jobs.run_daily_records --skip-drive
"""

import argparse
import os

from pwhl_btn.analytics.records import (
    check_recent_records,
    check_recent_hat_tricks,
    check_recent_first_goals,
    check_recent_point_streaks,
    check_recent_shutout_streaks,
)
from pwhl_btn.render.record_breaking import render_slides


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days",       type=int,  default=1,    help="Look-back window in days (default 1)")
    parser.add_argument("--dry-run",    action="store_true",     help="Detect events but skip rendering and upload")
    parser.add_argument("--skip-drive", action="store_true",     help="Skip Google Drive upload")
    args = parser.parse_args()

    print(f"\n-- Daily Record & Milestone Check (last {args.days} day(s)) --")

    # Collect all events
    all_contexts = []

    print("\n  [1/5] Checking season records...")
    records = check_recent_records(days=args.days)
    print(f"        {len(records)} record(s) found")
    all_contexts.extend(records)

    print("  [2/5] Checking hat tricks...")
    hat_tricks = check_recent_hat_tricks(days=args.days)
    print(f"        {len(hat_tricks)} hat trick(s) found")
    all_contexts.extend(hat_tricks)

    print("  [3/5] Checking first career goals...")
    first_goals = check_recent_first_goals(days=args.days)
    print(f"        {len(first_goals)} first goal(s) found")
    all_contexts.extend(first_goals)

    print("  [4/5] Checking player point streaks...")
    point_streaks = check_recent_point_streaks(days=args.days)
    print(f"        {len(point_streaks)} point streak record(s) found")
    all_contexts.extend(point_streaks)

    print("  [5/5] Checking goalie shutout streaks...")
    shutout_streaks = check_recent_shutout_streaks(days=args.days)
    print(f"        {len(shutout_streaks)} shutout streak record(s) found")
    all_contexts.extend(shutout_streaks)

    if not all_contexts:
        print(f"\n  Nothing notable in the last {args.days} day(s). Exiting.")
        return

    print(f"\n  Total: {len(all_contexts)} event(s) to render")

    if args.dry_run:
        for ctx in all_contexts:
            print(f"  [dry-run] {ctx['record_id']} — {ctx['record_name']} ({ctx['new_value']} {ctx['new_value_unit']})")
        return

    # Render and optionally upload each event
    all_outputs = []
    for ctx in all_contexts:
        print(f"\n  [{ctx['record_id']}]  {ctx['record_name']}  ({ctx['new_value']} {ctx['new_value_unit']})")
        outputs = render_slides(ctx)
        all_outputs.extend(outputs)

        if not args.skip_drive:
            _upload(outputs)

    print(f"\n  Done — {len(all_outputs)} slide(s) rendered across {len(all_contexts)} event(s)")


def _upload(outputs):
    try:
        from pwhl_btn.integrations.google_drive import upload_files
        folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "")
        if folder_id:
            links = upload_files(outputs, folder_id)
            print(f"  Uploaded {len(links)} file(s) to Drive")
    except Exception as e:
        print(f"  [Drive] {e}")


if __name__ == "__main__":
    main()
