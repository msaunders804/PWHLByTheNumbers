#!/usr/bin/env python3
"""
PWHL Weekly Preview Template Renderer
Renders weekly_preview.html with real data and exports a 1080x1920 PNG.

Usage:
    python3 render_weekly_preview.py                  # Uses sample data
    python3 render_weekly_preview.py --from-db        # Pulls from your PostgreSQL pipeline
    python3 render_weekly_preview.py --output /path/to/output.png
"""

import argparse
import os
from pathlib import Path
from datetime import datetime, timedelta

from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

# ── Paths ────────────────────────────────────────────────────────────────────
TEMPLATE_DIR = Path(__file__).parent / "templates"
OUTPUT_DIR   = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── Team logo paths (update these to your actual logo file paths) ─────────────
# Keys should match however your DB stores team names/abbreviations
TEAM_LOGOS = {
    "BOS": "assets/logos/BOS_50x50.png",
    "MIN": "assets/logos/MIN_50x50.png",
    "MTL": "assets/logos/MTL_50x50.png",
    "NYR": "assets/logos/NY_50x50.png",
    "OTT": "assets/logos/OTT_50x50.png",
    "SEA": "assets/logos/SEA_50x50.png",
    "TOR": "assets/logos/TOR_50x50.png",
    "VAN": "assets/logos/VAN_50x50.png",
}

TEAM_FULL_NAMES = {
    "BOS": "Boston",
    "MIN": "Minnesota",
    "MTL": "Montreal",
    "NYR": "New York",
    "OTT": "Ottawa",
    "SEA": "Seattle",
    "TOR": "Toronto",
    "VAN": "Vancouver",
}

# ── Must-watch scoring logic ─────────────────────────────────────────────────
def pick_mustwatch(games: list[dict]) -> dict | None:
    """
    Score each game and return the most compelling one as the must-watch.
    Plug in real logic from your DB (standings, rivalry history, streaks, etc.)
    
    Scoring factors (customize weights as needed):
      - Division/rivalry matchup
      - Both teams in playoff contention
      - Recent head-to-head closeness
      - Star player matchup
    """
    if not games:
        return None

    def score_game(game):
        score = 0
        # Example: Prime time games are higher profile
        if "7" in game["time"] or "8" in game["time"]:
            score += 1
        # Extend this with real DB queries:
        # score += rivalry_factor(game["home_abbr"], game["away_abbr"])
        # score += contention_factor(home_points, away_points)
        # score += h2h_closeness(game["home_abbr"], game["away_abbr"])
        return score

    ranked = sorted(games, key=score_game, reverse=True)
    winner = ranked[0]

    return {
        "game_id":   winner["game_id"],
        "home_team": winner["home_team"],
        "away_team": winner["away_team"],
        "date":      winner["date_short"],
        "time":      winner["time"],
        # Replace this with an AI-generated or template reason from your pipeline
        "reason":    f"A pivotal matchup between {winner['home_team']} and {winner['away_team']} "
                     f"with major playoff implications on the line.",
    }

# ── Data builders ─────────────────────────────────────────────────────────────
def build_game(game_id, home_abbr, away_abbr, date_short, time_str, date_iso) -> dict:
    """Helper to construct a game dict from abbreviations."""
    home_logo_path = TEAM_LOGOS.get(home_abbr, "")
    away_logo_path = TEAM_LOGOS.get(away_abbr, "")

    # Convert relative paths to absolute file:// URIs for Playwright
    def to_file_uri(path):
        if path and Path(path).exists():
            return Path(path).resolve().as_uri()
        return None

    return {
        "game_id":   game_id,
        "home_abbr": home_abbr,
        "away_abbr": away_abbr,
        "home_team": TEAM_FULL_NAMES.get(home_abbr, home_abbr),
        "away_team": TEAM_FULL_NAMES.get(away_abbr, away_abbr),
        "home_logo": to_file_uri(home_logo_path),
        "away_logo": to_file_uri(away_logo_path),
        "date_short": date_short,
        "time":       time_str,
        "date_iso":   date_iso,
    }


def get_sample_data() -> dict:
    """
    Sample data matching your Canva mockup.
    Replace this function with get_db_data() once connected to your pipeline.
    """
    games = [
        build_game("g1", "NYR", "TOR", "TUE 1/6",  "7 EST",  "2026-01-06"),
        build_game("g2", "SEA", "MIN", "WED 1/7",  "7 EST",  "2026-01-07"),
        build_game("g3", "VAN", "MTL", "FRI 1/9",  "7 EST",  "2026-01-09"),
        build_game("g4", "OTT", "MTL", "SUN 1/11", "12 EST", "2026-01-11"),
        build_game("g5", "TOR", "BOS", "SUN 1/11", "2 EST",  "2026-01-11"),
        build_game("g6", "MIN", "NYR", "SUN 1/11", "2 EST",  "2026-01-11"),
    ]
    return {
        "season":     "2025–26",
        "week_range": "JAN 6 – JAN 11",
        "games":      games,
        "mustwatch":  pick_mustwatch(games),
        "theme":      "light",
    }


def get_db_data() -> dict:
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from db_queries import get_template_data
        data = get_template_data()
        # Preview uses upcoming games, not last week's results
        games = data.get("upcoming", [])
        # Build preview-shaped game dicts
        preview_games = []
        for g in games:
            preview_games.append(build_game(
                game_id    = str(g["game_id"]),
                home_abbr  = g["home_abbr"],
                away_abbr  = g["away_abbr"],
                date_short = g["date_short"],
                time_str   = None,
                date_iso   = None,
            ))
        print(f"  [DB] {len(preview_games)} upcoming games loaded")
        return {
            "season":     data["season"],
            "week_range": data["week_range"],
            "games":      preview_games,
            "mustwatch":  pick_mustwatch(preview_games),
        }
    except Exception as e:
        print(f"  [DB ERROR] {e} — falling back to sample data")
        import traceback; traceback.print_exc()
        return get_sample_data()


# ── Renderer ──────────────────────────────────────────────────────────────────
def render(data: dict, output_path: Path) -> Path:
    """Render the Jinja2 template and screenshot it with Playwright."""

    # 1. Render HTML from template
    env  = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    tmpl = env.get_template("weekly_preview.html")
    html = tmpl.render(**data)

    # Write rendered HTML to a temp file so Playwright can load it
    html_path = OUTPUT_DIR / "_preview_render.html"
    html_path.write_text(html, encoding="utf-8")

    # 2. Screenshot with Playwright at exact dimensions
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1920})
        page.goto(f"file://{html_path.resolve()}")
        page.wait_for_timeout(800)  # Allow fonts/images to load
        page.screenshot(path=str(output_path), full_page=False)
        browser.close()

    print(f"✅ Rendered → {output_path}")
    return output_path


# ── CLI ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Render PWHL Weekly Preview graphic")
    parser.add_argument("--from-db", action="store_true", help="Pull data from PostgreSQL pipeline")
    parser.add_argument("--output",  type=str, default=None, help="Output PNG path")
    parser.add_argument("--theme",   type=str, default="light", choices=["light", "dark"],
                        help="Color theme: light (default) or dark")
    args = parser.parse_args()

    data = get_sample_data() if args.sample else get_db_data()
    data["theme"] = args.theme  # passed into Jinja2 as {{ theme }} body class

    timestamp   = datetime.now().strftime("%Y%m%d_%H%M")
    suffix      = f"_{args.theme}" if args.theme == "dark" else ""
    output_path = Path(args.output) if args.output else OUTPUT_DIR / f"weekly_preview{suffix}_{timestamp}.png"

    render(data, output_path)


if __name__ == "__main__":
    main()
