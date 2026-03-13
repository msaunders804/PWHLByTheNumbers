#!/usr/bin/env python3
"""
PWHL Weekly Recap Renderer
Produces 4 PNG slides: hook, scores, standings, and story of the week.

Usage:
    python -m pwhl_btn.render.weekly_recap --sample
    python -m pwhl_btn.render.weekly_recap --theme dark
    python -m pwhl_btn.render.weekly_recap
    python -m pwhl_btn.render.weekly_recap --override-event
"""

import argparse
import os
from pathlib import Path
from datetime import datetime

from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parents[2]

TEMPLATE_DIR = BASE_DIR.parent / "render" / "templates"
ASSETS_DIR = REPO_ROOT / "assets"
OUTPUT_DIR = REPO_ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

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


def _pwhl_logo_uri():
    for ext in ("png", "svg", "jpg", "webp"):
        p = ASSETS_DIR / "logos" / f"PWHL_logo.{ext}"
        if p.exists():
            return p.resolve().as_uri()
    return None


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


# ── Helpers ──────────────────────────────────────────────────────────────────
def logo_uri(abbr: str) -> str | None:
    rel_path = TEAM_LOGOS.get(abbr, "")
    full_path = REPO_ROOT / rel_path if rel_path else None
    if full_path and full_path.exists():
        return full_path.resolve().as_uri()
    return None


def initials(name: str) -> str:
    parts = name.split()
    return "".join(p[0] for p in parts if p)[:2].upper()


# ── Event scoring (auto-pick) ────────────────────────────────────────────────
EVENT_ICONS = {
    "HAT_TRICK": "🎩",
    "MILESTONE": "⭐",
    "POINT_STREAK": "🔥",
    "SEASON_FIRST": "👑",
    "CAREER_RECORD": "🏒",
    "SHUTOUT": "🧱",
    "COMEBACK_WIN": "⚡",
}

EVENT_LABELS = {
    "HAT_TRICK": "Hat Trick",
    "MILESTONE": "Milestone",
    "POINT_STREAK": "Point Streak",
    "SEASON_FIRST": "Season First",
    "CAREER_RECORD": "Career Record",
    "SHUTOUT": "Shutout",
    "COMEBACK_WIN": "Comeback Win",
}

EVENT_PRIORITY = list(EVENT_ICONS.keys())


def pick_event(flagged_events: list[dict]) -> dict | None:
    """
    Auto-pick the most significant event from milestone detector output.
    """
    if not flagged_events:
        return None

    ranked = sorted(
        flagged_events,
        key=lambda e: EVENT_PRIORITY.index(e["type"]) if e["type"] in EVENT_PRIORITY else 99,
    )
    e = ranked[0]
    e.setdefault("icon", EVENT_ICONS.get(e["type"], "📊"))
    e.setdefault("type_label", EVENT_LABELS.get(e["type"], e["type"].replace("_", " ").title()))
    e.setdefault("is_override", False)
    e.setdefault("player_photo", None)
    e.setdefault("player_initials", initials(e.get("player_name", "??")))
    return e


def manual_override_event() -> dict:
    print("\n── Manual Event Override ──")
    player_name = input("Player name: ").strip()
    player_team = input("Team: ").strip()
    player_pos = input("Position (e.g. F, D, G): ").strip()
    event_type = input(f"Event type {list(EVENT_ICONS.keys())}: ").strip().upper()
    headline = input("Headline (use <em>text</em> for purple highlights): ").strip()
    body = input("Body text (1-2 sentences): ").strip()

    stats = []
    print("Enter up to 3 stats (label then value). Leave label blank to stop.")
    for _ in range(3):
        lbl = input("  Stat label: ").strip()
        if not lbl:
            break
        val = input("  Stat value: ").strip()
        stats.append({"label": lbl, "value": val})

    return {
        "type": event_type,
        "icon": EVENT_ICONS.get(event_type, "📊"),
        "type_label": EVENT_LABELS.get(event_type, event_type.replace("_", " ").title()),
        "is_override": True,
        "player_name": player_name,
        "player_team": player_team,
        "player_position": player_pos,
        "player_photo": None,
        "player_initials": initials(player_name),
        "stats": stats,
        "headline": headline,
        "body": body,
    }


# ── Sample data ───────────────────────────────────────────────────────────────
def get_sample_data() -> dict:
    games = [
        {
            "date_short": "MON 1/6",
            "home_abbr": "NYR",
            "away_abbr": "TOR",
            "home_team": "New York",
            "away_team": "Toronto",
            "home_score": 3,
            "away_score": 1,
            "result_type": "REG",
            "home_logo": logo_uri("NYR"),
            "away_logo": logo_uri("TOR"),
        },
        {
            "date_short": "WED 1/8",
            "home_abbr": "SEA",
            "away_abbr": "MIN",
            "home_team": "Seattle",
            "away_team": "Minnesota",
            "home_score": 2,
            "away_score": 3,
            "result_type": "OT",
            "home_logo": logo_uri("SEA"),
            "away_logo": logo_uri("MIN"),
        },
        {
            "date_short": "FRI 1/10",
            "home_abbr": "VAN",
            "away_abbr": "MTL",
            "home_team": "Vancouver",
            "away_team": "Montreal",
            "home_score": 4,
            "away_score": 2,
            "result_type": "REG",
            "home_logo": logo_uri("VAN"),
            "away_logo": logo_uri("MTL"),
        },
        {
            "date_short": "SUN 1/12",
            "home_abbr": "OTT",
            "away_abbr": "BOS",
            "home_team": "Ottawa",
            "away_team": "Boston",
            "home_score": 1,
            "away_score": 2,
            "result_type": "SO",
            "home_logo": logo_uri("OTT"),
            "away_logo": logo_uri("BOS"),
        },
    ]

    standings = [
        {
            "abbr": "MIN",
            "name": "Minnesota",
            "logo": logo_uri("MIN"),
            "gp": 22,
            "wins": 15,
            "losses": 5,
            "otw": 1,
            "otl": 1,
            "home_record": "8-2",
            "away_record": "7-3",
            "points": 47,
        },
        {
            "abbr": "NYR",
            "name": "New York",
            "logo": logo_uri("NYR"),
            "gp": 22,
            "wins": 13,
            "losses": 6,
            "otw": 2,
            "otl": 1,
            "home_record": "7-3",
            "away_record": "6-3",
            "points": 42,
        },
        {
            "abbr": "BOS",
            "name": "Boston",
            "logo": logo_uri("BOS"),
            "gp": 21,
            "wins": 12,
            "losses": 6,
            "otw": 1,
            "otl": 2,
            "home_record": "6-3",
            "away_record": "6-3",
            "points": 39,
        },
        {
            "abbr": "TOR",
            "name": "Toronto",
            "logo": logo_uri("TOR"),
            "gp": 22,
            "wins": 11,
            "losses": 8,
            "otw": 1,
            "otl": 2,
            "home_record": "6-4",
            "away_record": "5-4",
            "points": 36,
        },
        {
            "abbr": "OTT",
            "name": "Ottawa",
            "logo": logo_uri("OTT"),
            "gp": 21,
            "wins": 10,
            "losses": 8,
            "otw": 2,
            "otl": 1,
            "home_record": "5-4",
            "away_record": "5-4",
            "points": 35,
        },
        {
            "abbr": "MTL",
            "name": "Montreal",
            "logo": logo_uri("MTL"),
            "gp": 22,
            "wins": 9,
            "losses": 10,
            "otw": 1,
            "otl": 2,
            "home_record": "5-5",
            "away_record": "4-5",
            "points": 31,
        },
        {
            "abbr": "VAN",
            "name": "Vancouver",
            "logo": logo_uri("VAN"),
            "gp": 22,
            "wins": 7,
            "losses": 12,
            "otw": 1,
            "otl": 2,
            "home_record": "4-6",
            "away_record": "3-6",
            "points": 25,
        },
        {
            "abbr": "SEA",
            "name": "Seattle",
            "logo": logo_uri("SEA"),
            "gp": 21,
            "wins": 5,
            "losses": 14,
            "otw": 1,
            "otl": 1,
            "home_record": "3-7",
            "away_record": "2-7",
            "points": 19,
        },
    ]

    event = pick_event(
        [
            {
                "type": "HAT_TRICK",
                "player_name": "Marie-Philip Poulin",
                "player_team": "Montreal",
                "player_position": "F",
                "player_photo": None,
                "team_logo": logo_uri("MTL"),
                "stats": [
                    {"label": "Goals", "value": "3"},
                    {"label": "Assists", "value": "1"},
                    {"label": "Points", "value": "4"},
                ],
                "headline": "<em>Poulin</em> Lights the Lamp Three Times in Dominant Montreal Performance",
                "body": (
                    "Marie-Philip Poulin recorded her first hat trick of the season Friday night, "
                    "adding an assist for a 4-point game that moved Montreal within 4 points of the playoff line."
                ),
            }
        ]
    )

    total_goals = sum(g["home_score"] + g["away_score"] for g in games)
    top_team = standings[0]
    teaser = {
        "games_played": len(games),
        "stat_line": f"<em>{total_goals}</em> goals scored",
        "leader_name": top_team["name"],
        "leader_stat": f"{top_team['points']} PTS",
    }

    return {
        "season": "2025–26",
        "week_range": "JAN 6 – JAN 12",
        "week_end": "JAN 12, 2026",
        "theme": "light",
        "games": games,
        "standings": standings,
        "event": event,
        "teaser": teaser,
        "skater_photo": None,
        "skater_name": None,
        "skater_team": None,
        "pwhl_logo": _pwhl_logo_uri(),
    }


# ── DB data ──────────────────────────────────────────────────────────────────
def get_db_data() -> dict:
    from pwhl_btn.db.db_queries import get_template_data

    data = get_template_data()
    print(f"  [DB] {len(data['games'])} games, {len(data['standings'])} teams loaded")
    data.setdefault("skater_photo", None)
    data.setdefault("skater_name", None)
    data.setdefault("skater_team", None)
    data.setdefault("pwhl_logo", _pwhl_logo_uri())
    return data


# ── Renderer ─────────────────────────────────────────────────────────────────
def render_slide(template_name: str, data: dict, output_path: Path) -> Path:
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    tmpl = env.get_template(template_name)
    html = tmpl.render(**data)

    html_path = OUTPUT_DIR / f"_render_{template_name}"
    html_path.write_text(html, encoding="utf-8")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1920})
        page.goto(f"file://{html_path.resolve()}")
        page.wait_for_timeout(800)
        page.screenshot(path=str(output_path), full_page=False)
        browser.close()

    print(f"  ✅ {output_path.name}")
    return output_path


def render_all(data: dict, out_dir: Path) -> list[Path]:
    slides = [
        ("recap_slide0.html", "recap_0_hook.png"),
        ("recap_slide1.html", "recap_1_scores.png"),
        ("recap_slide2.html", "recap_2_standings.png"),
        ("recap_slide3.html", "recap_3_story.png"),
    ]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    outputs = []
    print(f"\n🎬 Rendering Weekly Recap — {data['week_range']}")

    for tmpl, fname in slides:
        path = out_dir / fname.replace(".png", f"_{timestamp}.png")
        render_slide(tmpl, data, path)
        outputs.append(path)

    print(f"\n✨ Done — {len(outputs)} slides saved to {out_dir}")
    return outputs


# ── CLI ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Render PWHL Weekly Recap (4 slides)")
    parser.add_argument("--from-db", action="store_true", default=True)
    parser.add_argument("--sample", action="store_true", help="Use sample data instead of DB")
    parser.add_argument("--theme", default="light", choices=["light", "dark"])
    parser.add_argument("--override-event", action="store_true", help="Manually specify the Story of the Week")
    parser.add_argument("--out-dir", type=str, default=None)
    parser.add_argument("--skater-photo", type=str, default=None, help="Path to skater photo for slide 1")
    parser.add_argument("--skater-name", type=str, default=None)
    parser.add_argument("--skater-team", type=str, default=None)
    parser.add_argument("--skip-drive", action="store_true")
    args = parser.parse_args()

    data = get_sample_data() if args.sample else get_db_data()
    data["theme"] = args.theme

    if args.skater_photo:
        p = Path(args.skater_photo)
        data["skater_photo"] = p.resolve().as_uri() if p.exists() else args.skater_photo
    if args.skater_name:
        data["skater_name"] = args.skater_name
    if args.skater_team:
        data["skater_team"] = args.skater_team

    if data.get("skater_name") and not args.skater_name:
        print(f"  [Slide 1] Auto-selected: {data['skater_name']} ({data['skater_team']})")
        if data.get("skater_photo"):
            print(f"  [Slide 1] Photo found: {data['skater_photo']}")
        else:
            print(f"  [Slide 1] No photo found for {data['skater_name']} — placeholder will show")

    if args.override_event:
        data["event"] = manual_override_event()
        data["event"]["is_override"] = True

    out_dir = Path(args.out_dir) if args.out_dir else OUTPUT_DIR
    outputs = render_all(data, out_dir)

    if not args.skip_drive:
        folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "")
        if folder_id and outputs:
            try:
                from pwhl_btn.integrations.google_drive import upload_files
                links = upload_files(outputs, folder_id)
                print(f"  📁 Uploaded {len(links)} slides to Drive")
            except Exception as e:
                print(f"  Drive upload failed: {e}")


if __name__ == "__main__":
    main()