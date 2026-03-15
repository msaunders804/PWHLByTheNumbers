"""
monte_carlo_slides.py — Monte Carlo simulation TikTok slides.

Slide 0: The Road to the Walter Cup (hook)
Slide 1: Playoff Predictions (likelihood to make playoffs)
Slide 2: Walter Cup Odds (bar chart for all 8 teams)
Slide 3: How Monte Carlo works (explainer)

Usage:
    python -m pwhl_btn.render.monte_carlo_slides            # live data
    python -m pwhl_btn.render.monte_carlo_slides --sample   # no DB required
    python -m pwhl_btn.render.monte_carlo_slides --skip-drive
"""

import argparse
import os
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright
from datetime import datetime

TOTAL_SEASON_GAMES = 30

BASE_DIR     = Path(__file__).parent
TEMPLATE_DIR = BASE_DIR / "templates"
OUTPUT_DIR   = BASE_DIR.parent.parent.parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def _load_dotenv():
    for env_path in [
        BASE_DIR / ".env",
        BASE_DIR.parent / ".env",
        BASE_DIR.parent.parent / ".env",
        BASE_DIR.parent.parent.parent / ".env",
    ]:
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


def _sim_label() -> str:
    return date.today().strftime("%B %d, %Y").upper()


def get_sample_data() -> dict:
    """Sample data for testing without DB access."""
    raw = [
        {"team_code": "MTL", "current_pts": 52, "games_remaining": 12,
         "playoff_pct": 97.4, "walter_cup_pct": 38.2,
         "proj_pts_mean": 66.1, "proj_pts_low": 58, "proj_pts_high": 74},
        {"team_code": "BOS", "current_pts": 48, "games_remaining": 13,
         "playoff_pct": 91.8, "walter_cup_pct": 24.6,
         "proj_pts_mean": 62.8, "proj_pts_low": 55, "proj_pts_high": 71},
        {"team_code": "MIN", "current_pts": 44, "games_remaining": 13,
         "playoff_pct": 82.3, "walter_cup_pct": 17.1,
         "proj_pts_mean": 59.2, "proj_pts_low": 51, "proj_pts_high": 67},
        {"team_code": "TOR", "current_pts": 40, "games_remaining": 12,
         "playoff_pct": 68.5, "walter_cup_pct": 9.8,
         "proj_pts_mean": 54.4, "proj_pts_low": 47, "proj_pts_high": 62},
        {"team_code": "OTT", "current_pts": 37, "games_remaining": 13,
         "playoff_pct": 54.1, "walter_cup_pct": 6.4,
         "proj_pts_mean": 51.7, "proj_pts_low": 44, "proj_pts_high": 60},
        {"team_code": "NY",  "current_pts": 33, "games_remaining": 14,
         "playoff_pct": 38.7, "walter_cup_pct": 2.9,
         "proj_pts_mean": 48.5, "proj_pts_low": 40, "proj_pts_high": 57},
        {"team_code": "VAN", "current_pts": 26, "games_remaining": 13,
         "playoff_pct": 14.2, "walter_cup_pct": 0.8,
         "proj_pts_mean": 41.0, "proj_pts_low": 33, "proj_pts_high": 50},
        {"team_code": "SEA", "current_pts": 20, "games_remaining": 14,
         "playoff_pct": 5.8,  "walter_cup_pct": 0.2,
         "proj_pts_mean": 35.3, "proj_pts_low": 27, "proj_pts_high": 44},
    ]
    # Sort by Walter Cup %
    raw.sort(key=lambda x: x["walter_cup_pct"], reverse=True)

    from pwhl_btn.db.db_queries import _logo_uri, _pwhl_logo_uri, _walter_cup_uri
    try:
        for t in raw:
            t["logo"] = _logo_uri(t["team_code"])
        pwhl_logo      = _pwhl_logo_uri()
        walter_cup_img = _walter_cup_uri()
    except Exception:
        for t in raw:
            t["logo"] = None
        pwhl_logo      = None
        walter_cup_img = None

    avg_rem = round(sum(t["games_remaining"] for t in raw) / len(raw))
    season_pct = round((TOTAL_SEASON_GAMES - avg_rem) / TOTAL_SEASON_GAMES * 100)
    return {
        "teams":               raw,
        "sim_label":           _sim_label(),
        "games_remaining_avg": avg_rem,
        "season":              8,
        "pwhl_logo":           pwhl_logo,
        "walter_cup_img":      walter_cup_img,
        "season_pct":          season_pct,
    }


def get_live_data() -> dict:
    from pwhl_btn.analytics.monte_carlo import run_simulation
    from pwhl_btn.db.db_queries import _logo_uri, _pwhl_logo_uri, _walter_cup_uri

    print("  Running Monte Carlo simulation (10,000 runs)...")
    results = run_simulation(n=10_000)

    teams = []
    for tid, r in results.items():
        r["logo"] = _logo_uri(r["team_code"])
        teams.append(r)

    # Sort by Walter Cup probability (highest first)
    teams.sort(key=lambda x: x["walter_cup_pct"], reverse=True)

    avg_rem = round(sum(t["games_remaining"] for t in teams) / len(teams)) if teams else 0
    season_pct = round((TOTAL_SEASON_GAMES - avg_rem) / TOTAL_SEASON_GAMES * 100)

    return {
        "teams":               teams,
        "sim_label":           _sim_label(),
        "games_remaining_avg": avg_rem,
        "season":              8,
        "pwhl_logo":           _pwhl_logo_uri(),
        "walter_cup_img":      _walter_cup_uri(),
        "season_pct":          season_pct,
    }


def render_slides(data: dict) -> list[Path]:
    env       = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    outputs   = []

    slides = [
        ("mc_slide0.html", "hook"),
        ("mc_slide1.html", "playoff_odds"),
        ("mc_slide2.html", "walter_cup_odds"),
        ("mc_slide3.html", "explainer"),
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for tmpl_name, label in slides:
            template = env.get_template(tmpl_name)
            html     = template.render(**data)
            out_path = OUTPUT_DIR / f"monte_carlo_{label}_{timestamp}.png"

            tmp_html = OUTPUT_DIR / f"_render_{tmpl_name}"
            tmp_html.write_text(html, encoding="utf-8")

            page = browser.new_page(viewport={"width": 1080, "height": 1920})
            page.goto(f"file://{tmp_html.resolve()}")
            page.wait_for_timeout(800)
            page.screenshot(path=str(out_path), clip={"x": 0, "y": 0, "width": 1080, "height": 1920})
            page.close()
            tmp_html.unlink(missing_ok=True)
            print(f"  ✅ {out_path.name}")
            outputs.append(out_path)
        browser.close()

    return outputs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample",     action="store_true", help="Use sample data (no DB)")
    parser.add_argument("--skip-drive", action="store_true", help="Skip Google Drive upload")
    args = parser.parse_args()

    print("\n── Monte Carlo Slides ──────────────────────────────")
    data    = get_sample_data() if args.sample else get_live_data()
    outputs = render_slides(data)

    if not args.skip_drive:
        try:
            from pwhl_btn.integrations.google_drive import upload_files
            folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "")
            if folder_id:
                links = upload_files(outputs, folder_id)
                print(f"  📁 Uploaded {len(links)} files to Drive")
        except Exception as e:
            print(f"  [Drive] {e}")

    print(f"\n  Done — {len(outputs)} slides rendered")
    return outputs


if __name__ == "__main__":
    main()
