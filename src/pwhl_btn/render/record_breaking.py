"""
record_breaking.py — Render TikTok slides for a record-breaking game.

Data comes from analytics/records.py — this module only handles rendering.

Slide 0: Hook — teases the broken record and new value
Slide 1: Details — new record holder vs previous holders, optional player photo
Slide 2 (optional): Full point/scorer breakdown

Usage:
    # Check last 7 days and render any broken records
    python -m pwhl_btn.render.record_breaking

    # Wider look-back window
    python -m pwhl_btn.render.record_breaking --days 14

    # Skip the detail slide (2-slide version)
    python -m pwhl_btn.render.record_breaking --no-detail

    # Sample data (no DB required)
    python -m pwhl_btn.render.record_breaking --sample

    # Skip Drive upload
    python -m pwhl_btn.render.record_breaking --skip-drive
"""

import argparse
import os
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

BASE_DIR     = Path(__file__).parent
TEMPLATE_DIR = BASE_DIR / "templates"
OUTPUT_DIR   = BASE_DIR.parent.parent.parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

SEASON_ID = 8


# ── Sample data ────────────────────────────────────────────────────────────────

def get_sample_data() -> list[dict]:
    from pwhl_btn.db.db_queries import _logo_uri, _pwhl_logo_uri

    def _logo(code):
        try:
            return _logo_uri(code)
        except Exception:
            return None

    return [{
        "record_id":         "skaters_with_point_single_team",
        "record_name":       "MOST SKATERS WITH A POINT - SINGLE TEAM",
        "new_value":         12,
        "new_value_unit":    "SKATERS",
        "new_team_code":     "MIN",
        "new_team_name":     "Minnesota Frost",
        "new_team_logo":     _logo("MIN"),
        "new_game_result":   "6-2 W",
        "new_game_opponent": "OTT",
        "new_game_date":     "Mar 18, 2026",
        "player_photo":      None,
        "featured_player_name": None,
        "prev_value":        11,
        "prev_holders": [
            {"team_code": "MIN", "logo": _logo("MIN"), "game_date": "Dec 19, 2025", "opponent": "vs BOS", "score": "5-2"},
            {"team_code": "SEA", "logo": _logo("SEA"), "game_date": "Jan 20, 2026", "opponent": "vs TOR", "score": "6-4"},
            {"team_code": "NY",  "logo": _logo("NY"),  "game_date": "Nov 29, 2025", "opponent": "vs VAN", "score": "5-1"},
        ],
        "prev_holders_label": "MIN, SEA & NY",
        "scorers": [
            {"name": "Taylor Heise",    "goals": 2, "assists": 1, "points": 3},
            {"name": "Sophie Jaques",   "goals": 1, "assists": 2, "points": 3},
            {"name": "Grace Zumwinkle", "goals": 1, "assists": 1, "points": 2},
            {"name": "Kendall Coyne",   "goals": 0, "assists": 2, "points": 2},
            {"name": "Michela Cava",    "goals": 1, "assists": 0, "points": 1},
            {"name": "Hannah Brandt",   "goals": 0, "assists": 1, "points": 1},
            {"name": "Britta Curl",     "goals": 0, "assists": 1, "points": 1},
            {"name": "Olivia Knowles",  "goals": 0, "assists": 1, "points": 1},
            {"name": "Emma Condie",     "goals": 0, "assists": 1, "points": 1},
            {"name": "Clare Boyles",    "goals": 0, "assists": 1, "points": 1},
            {"name": "Audra Richards",  "goals": 0, "assists": 1, "points": 1},
            {"name": "Nicole Hensley",  "goals": 0, "assists": 1, "points": 1},
        ],
        "include_detail_slide": True,
        "season":    SEASON_ID,
        "pwhl_logo": _pwhl_logo_uri(),
    }]


# ── Renderer ───────────────────────────────────────────────────────────────────

def render_slides(data: dict, include_detail: bool = True) -> list[Path]:
    """Render all slides for a single record-break context. Returns output paths."""
    data = dict(data)  # don't mutate caller's dict
    data["include_detail_slide"] = include_detail and data.get("include_detail_slide", True)

    env       = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    record_id = data.get("record_id", "record")
    outputs   = []

    slides = [
        ("record_slide0.html", "hook"),
        ("record_slide1.html", "details"),
    ]
    if data["include_detail_slide"]:
        slides.append(("record_slide2.html", "breakdown"))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for tmpl_name, label in slides:
            template = env.get_template(tmpl_name)
            html     = template.render(**data)
            out_path = OUTPUT_DIR / f"record_{record_id}_{label}_{timestamp}.png"

            tmp_html = OUTPUT_DIR / f"_render_{tmpl_name}"
            tmp_html.write_text(html, encoding="utf-8")

            page = browser.new_page(viewport={"width": 1080, "height": 1920})
            page.goto(f"file://{tmp_html.resolve()}")
            page.wait_for_timeout(800)
            page.screenshot(path=str(out_path), clip={"x": 0, "y": 0, "width": 1080, "height": 1920})
            page.close()
            tmp_html.unlink(missing_ok=True)

            print(f"  [ok] {out_path.name}")
            outputs.append(out_path)
        browser.close()

    return outputs


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days",       type=int,  default=7,    help="Look-back window in days (default 7)")
    parser.add_argument("--no-detail",  action="store_true",     help="Omit slide 2 (scorer breakdown)")
    parser.add_argument("--sample",     action="store_true",     help="Use sample data (no DB)")
    parser.add_argument("--skip-drive", action="store_true",     help="Skip Google Drive upload")
    args = parser.parse_args()

    print("\n-- Record Breaking Game Slides --")

    if args.sample:
        all_contexts = get_sample_data()
    else:
        from pwhl_btn.analytics.records import check_recent_records
        all_contexts = check_recent_records(days=args.days)

    if not all_contexts:
        print(f"  No records broken in the last {args.days} days.")
        return []

    print(f"  {len(all_contexts)} broken record(s) found.")

    all_outputs = []
    for ctx in all_contexts:
        print(f"\n  [{ctx['record_id']}]  {ctx['new_value']} {ctx['new_value_unit']}  (prev: {ctx['prev_value']})")
        outputs = render_slides(ctx, include_detail=not args.no_detail)
        all_outputs.extend(outputs)

        if not args.skip_drive:
            try:
                from pwhl_btn.integrations.google_drive import upload_files
                folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "")
                if folder_id:
                    links = upload_files(outputs, folder_id)
                    print(f"  Uploaded {len(links)} files to Drive")
            except Exception as e:
                print(f"  [Drive] {e}")

    print(f"\n  Done -- {len(all_outputs)} slides rendered across {len(all_contexts)} record(s)")
    return all_outputs


if __name__ == "__main__":
    main()
