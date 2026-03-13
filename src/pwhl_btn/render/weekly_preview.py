"""
weekly_preview.py — Renders the Sunday night weekly preview (4 slides).

Location: src/pwhl_btn/render/weekly_preview.py

Usage:
    python render/weekly_preview.py
    python render/weekly_preview.py --skip-drive
"""

import argparse
import json
import os
import urllib.request
from datetime import datetime, timedelta, date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

# ── Paths ─────────────────────────────────────────────────────────────────────
# render/weekly_preview.py
#   → BASE_DIR    = src/pwhl_btn/render/
#   → PACKAGE_DIR = src/pwhl_btn/
RENDER_DIR   = Path(__file__).resolve().parent
PACKAGE_DIR  = RENDER_DIR.parent
TEMPLATE_DIR = RENDER_DIR / "templates"
OUTPUT_DIR   = PACKAGE_DIR.parent.parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)



def _load_dotenv():
    for env_path in [PACKAGE_DIR / ".env", PACKAGE_DIR.parent / ".env", PACKAGE_DIR.parent.parent / ".env"]:
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
            headers={
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
                "x-api-key": os.environ.get("ANTHROPIC_API_KEY", ""),
            },
            method="POST"
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
            return data["content"][0]["text"].strip()
    except Exception as e:
        print(f"  [Why watch] API error: {e}")
        return "Two of the league's most competitive teams clash with real playoff implications on the line."


def get_live_data() -> dict:
    from pwhl_btn.db.db_queries import get_upcoming_schedule, get_game_to_watch, get_preview_standings

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
            tmp_html = OUTPUT_DIR / f"_render_{tmpl_name}"
            tmp_html.write_text(html, encoding="utf-8")

            out_path = OUTPUT_DIR / f"preview_{label}_{timestamp}.png"
            page     = browser.new_page(viewport={"width": 1080, "height": 1920})
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
    parser.add_argument("--skip-drive", action="store_true")
    args = parser.parse_args()

    print("\n── Weekly Preview ──────────────────────────────")
    data    = get_live_data()
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