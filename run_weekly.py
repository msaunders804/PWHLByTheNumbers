"""
run_weekly.py — Master weekly recap script.
Chains: DB update → render slides → upload to Drive → SMS alert

Usage:
    python run_weekly.py              # full run
    python run_weekly.py --skip-sms   # skip SMS (for testing)
    python run_weekly.py --skip-drive # skip Drive upload
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

# ── Setup ─────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# Load .env if present (local runs)
def _load_dotenv():
    for env_path in [BASE_DIR / ".env", BASE_DIR.parent / ".env"]:
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, _, v = line.partition("=")
                    k = k.strip(); v = v.strip().strip('"').strip("'")
                    if k and k not in os.environ:
                        os.environ[k] = v

_load_dotenv()


def step(label: str):
    print(f"\n{'='*50}")
    print(f"  {label}")
    print(f"{'='*50}")


def run(skip_sms=False, skip_drive=False):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    errors = []

    # ── 1. Update DB ──────────────────────────────────────────────────────────
    step("1/4  Updating database")
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, str(BASE_DIR / "update.py")],
            capture_output=True, text=True
        )
        print(result.stdout)
        if result.returncode != 0:
            raise RuntimeError(result.stderr)
    except Exception as e:
        errors.append(f"DB update failed: {e}")
        print(f"  ERROR: {e}")

    # ── 2. Render slides ──────────────────────────────────────────────────────
    step("2/4  Rendering slides")
    slide_paths = []
    try:
        sys.path.insert(0, str(BASE_DIR))
        from render_weekly_recap import get_db_data, render_all
        data = get_db_data()
        slide_paths = render_all(data, OUTPUT_DIR)
        week_range = data.get("week_range", "this week")
    except Exception as e:
        errors.append(f"Render failed: {e}")
        print(f"  ERROR: {e}")
        week_range = "this week"

    # ── 3. Upload to Google Drive ─────────────────────────────────────────────
    drive_links = []
    folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")

    if not skip_drive and slide_paths and folder_id:
        step("3/4  Uploading to Google Drive")
        try:
            from drive_upload import upload_files
            drive_links = upload_files(slide_paths, folder_id)
        except Exception as e:
            errors.append(f"Drive upload failed: {e}")
            print(f"  ERROR: {e}")
    else:
        step("3/4  Skipping Drive upload")

    # ── 4. Send SMS ───────────────────────────────────────────────────────────
    if not skip_sms:
        step("4/4  Sending SMS alert")
        try:
            from notify import send_sms

            if errors:
                msg = (f"⚠️ BTN Weekly Recap — {week_range}\n"
                       f"{len(slide_paths)} slides | {len(errors)} error(s)\n"
                       f"Check GitHub Actions for details.")
            elif drive_links:
                msg = (f"✅ BTN Weekly Recap ready — {week_range}\n"
                       f"{len(slide_paths)} slides uploaded to Drive.\n"
                       f"Open: {drive_links[0]}")
            else:
                msg = (f"✅ BTN Weekly Recap rendered — {week_range}\n"
                       f"{len(slide_paths)} slides in GitHub Actions artifacts.")

            send_sms(msg)
        except Exception as e:
            print(f"  SMS ERROR: {e}")
    else:
        step("4/4  Skipping SMS")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*50}")
    print(f"  DONE — {len(slide_paths)} slides | {len(errors)} errors")
    if errors:
        for e in errors:
            print(f"  ✗ {e}")
    print(f"{'='*50}\n")

    return len(errors) == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-sms",   action="store_true")
    parser.add_argument("--skip-drive", action="store_true")
    args = parser.parse_args()

    success = run(skip_sms=args.skip_sms, skip_drive=args.skip_drive)
    sys.exit(0 if success else 1)
