"""
render_weekly_preview.py — Renders the Sunday night weekly preview (4 slides).

Usage:
    python render_weekly_preview.py            # live data from DB
    python render_weekly_preview.py --sample   # sample data (no DB)
    python render_weekly_preview.py --skip-drive
"""

import argparse
import json
import os
import urllib.request
from datetime import datetime, timedelta, date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

BASE_DIR     = Path(__file__).parent
TEMPLATE_DIR = BASE_DIR / "templates"
OUTPUT_DIR   = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


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


def _next_week_range():
    today          = date.today()
    days_to_monday = (7 - today.weekday()) % 7 or 7
    start          = today + timedelta(days=days_to_monday)
    end            = start + timedelta(days=6)
    return start, end


def _week_label(start, end):
    if start.month == end.month:
        return f"{start.strftime('%B %d')} – {end.strftime('%d, %Y')}"
    return f"{start.strftime('%b %d')} – {end.strftime('%b %d, %Y')}"


def _current_week_num(start_date):
    season_start = date(2025, 11, 21)
    return ((start_date - season_start).days // 7) + 1


def generate_why_watch(home_team, away_team, home_record, away_record, key_players) -> str:
    try:
        players_str = ", ".join(p["name"] for p in key_players[:3])
        prompt = (
            f"Write 2 short punchy sentences explaining why PWHL fans should watch "
            f"{away_team} ({away_record}) vs {home_team} ({home_record}). "
            f"Key players include {players_str}. "
            f"Focus on standings stakes, rivalry, or player storylines. "
            f"No emojis. No quotes. Conversational tone."
        )
        payload = json.dumps({
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 120,
            "messages": [{"role": "user", "content": prompt}]
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={"Content-Type": "application/json", "anthropic-version": "2023-06-01"},
            method="POST"
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
            return data["content"][0]["text"].strip()
    except Exception as e:
        print(f"  [Why watch] API error: {e}")
        return "Two of the league's most competitive teams clash with real playoff implications on the line."


def get_sample_data() -> dict:
    start = date.today() + timedelta(days=1)
    end   = start + timedelta(days=6)
    return {
        "week_label":          "WEEK 15",
        "week_range":          _week_label(start, end).upper(),
        "games_count":         6,
        "teams_count":         8,
        "game_to_watch_short": "BOS vs MTL",
        "pwhl_logo":           None,
        "schedule_days": [
            {"day_name": "TUESDAY",  "date_str": "MAR 10", "games": [
                {"away_team": "BOS", "home_team": "TOR", "away_logo": None, "home_logo": None, "time": "7:00 PM ET", "broadcast": "TSN"},
                {"away_team": "MIN", "home_team": "OTT", "away_logo": None, "home_logo": None, "time": "7:00 PM ET", "broadcast": ""},
            ]},
            {"day_name": "THURSDAY", "date_str": "MAR 12", "games": [
                {"away_team": "SEA", "home_team": "VAN", "away_logo": None, "home_logo": None, "time": "9:00 PM ET", "broadcast": "PWHL+"},
            ]},
            {"day_name": "SATURDAY", "date_str": "MAR 14", "games": [
                {"away_team": "BOS", "home_team": "MTL", "away_logo": None, "home_logo": None, "time": "3:00 PM ET", "broadcast": "CBC"},
                {"away_team": "NY",  "home_team": "MIN", "away_logo": None, "home_logo": None, "time": "5:00 PM ET", "broadcast": "PWHL+"},
            ]},
            {"day_name": "SUNDAY",   "date_str": "MAR 15", "games": [
                {"away_team": "TOR", "home_team": "OTT", "away_logo": None, "home_logo": None, "time": "2:00 PM ET", "broadcast": "TSN"},
            ]},
        ],
        "gtw_home_team":   "MTL", "gtw_away_team":   "BOS",
        "gtw_home_logo":   None,  "gtw_away_logo":   None,
        "gtw_home_record": "18-8-3", "gtw_away_record": "17-9-2",
        "gtw_date":        "SAT MAR 14", "gtw_time": "3:00 PM ET",
        "why_watch": "Boston and Montreal sit just two points apart in the standings, making this a preview of a potential playoff series. Maschmeyer and Desbiens are the two hottest goalies in the league right now.",
        "key_players": [
            {"name": "Marie-Philip Poulin", "team": "MTL", "goals": 14, "assists": 18, "points": 32},
            {"name": "Kristin O'Neill",     "team": "MTL", "goals": 10, "assists": 15, "points": 25},
            {"name": "Hilary Knight",       "team": "BOS", "goals": 12, "assists": 16, "points": 28},
            {"name": "Alina Mueller",       "team": "BOS", "goals": 8,  "assists": 19, "points": 27},
        ],
        "standings": [
            {"name": "MTL", "logo": None, "wins": 18, "losses": 8,  "ot_losses": 3, "gp": 29, "points": 39, "status": "playoff"},
            {"name": "BOS", "logo": None, "wins": 17, "losses": 9,  "ot_losses": 2, "gp": 28, "points": 36, "status": "playoff"},
            {"name": "MIN", "logo": None, "wins": 15, "losses": 10, "ot_losses": 4, "gp": 29, "points": 34, "status": "playoff"},
            {"name": "TOR", "logo": None, "wins": 14, "losses": 11, "ot_losses": 4, "gp": 29, "points": 32, "status": "playoff"},
            {"name": "OTT", "logo": None, "wins": 13, "losses": 12, "ot_losses": 4, "gp": 29, "points": 30, "status": "bubble"},
            {"name": "NY",  "logo": None, "wins": 12, "losses": 13, "ot_losses": 3, "gp": 28, "points": 27, "status": "bubble"},
            {"name": "VAN", "logo": None, "wins": 9,  "losses": 16, "ot_losses": 4, "gp": 29, "points": 22, "status": "out"},
            {"name": "SEA", "logo": None, "wins": 7,  "losses": 18, "ot_losses": 3, "gp": 28, "points": 17, "status": "out"},
        ],
    }


def get_live_data() -> dict:
    import sys
    sys.path.insert(0, str(BASE_DIR / "pwhl"))
    from db_queries import get_upcoming_schedule, get_game_to_watch, get_preview_standings

    start, end = _next_week_range()
    print(f"  Week: {start} → {end}")

    schedule  = get_upcoming_schedule(start, end)
    gtw       = get_game_to_watch(start, end)
    standings = get_preview_standings()

    games_count     = sum(len(d["games"]) for d in schedule)
    teams_in_action = len({t for d in schedule for g in d["games"]
                           for t in [g["away_team"], g["home_team"]]})

    if gtw:
        print(f"  Generating why-watch for {gtw['gtw_away_team']} @ {gtw['gtw_home_team']}...")
        gtw["why_watch"] = generate_why_watch(
            gtw["gtw_home_team"], gtw["gtw_away_team"],
            gtw["gtw_home_record"], gtw["gtw_away_record"],
            gtw["key_players"]
        )

    data = {
        "week_label":          f"WEEK {_current_week_num(start)}",
        "week_range":          _week_label(start, end).upper(),
        "games_count":         games_count,
        "teams_count":         teams_in_action,
        "game_to_watch_short": f"{gtw['gtw_away_team']} vs {gtw['gtw_home_team']}" if gtw else "TBD",
        "pwhl_logo":           None,
        "schedule_days":       schedule,
        "standings":           standings,
    }
    if gtw:
        data.update(gtw)
    return data


def render_slides(data: dict) -> list:
    env       = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    outputs   = []

    slides = [
        ("preview_slide0.html", "hook"),
        ("preview_slide1.html", "schedule"),
        ("preview_slide2.html", "gametowatch"),
        ("preview_slide3.html", "standings"),
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for tmpl_name, label in slides:
            template = env.get_template(tmpl_name)
            html     = template.render(**data)
            out_path = OUTPUT_DIR / f"preview_{label}_{timestamp}.png"
            page     = browser.new_page(viewport={"width": 1080, "height": 1920})
            page.set_content(html, wait_until="networkidle")
            page.screenshot(path=str(out_path), clip={"x": 0, "y": 0, "width": 1080, "height": 1920})
            page.close()
            print(f"  ✅ {out_path.name}")
            outputs.append(out_path)
        browser.close()

    return outputs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample",     action="store_true")
    parser.add_argument("--skip-drive", action="store_true")
    args = parser.parse_args()

    print("\n── Weekly Preview ──────────────────────────────")
    data    = get_sample_data() if args.sample else get_live_data()
    outputs = render_slides(data)

    if not args.skip_drive:
        try:
            from drive_upload import upload_files
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
