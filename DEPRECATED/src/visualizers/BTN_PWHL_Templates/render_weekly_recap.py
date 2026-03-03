#!/usr/bin/env python3
"""
PWHL Weekly Recap Renderer
Produces 3 PNG slides: scores, standings, story of the week.

Usage:
    python3 render_weekly_recap.py                   # sample data, light theme
    python3 render_weekly_recap.py --theme dark
    python3 render_weekly_recap.py --from-db
    python3 render_weekly_recap.py --override-event  # prompts for manual story override
"""

import argparse
import json
import os
from pathlib import Path
from datetime import datetime, timedelta

from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

# ── Paths ────────────────────────────────────────────────────────────────────
TEMPLATE_DIR = Path(__file__).parent / "templates"
OUTPUT_DIR   = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

TEAM_LOGOS = {
    "BOS": "assets/logos/boston.png",
    "MIN": "assets/logos/minnesota.png",
    "MTL": "assets/logos/montreal.png",
    "NYR": "assets/logos/newyork.png",
    "OTT": "assets/logos/ottawa.png",
    "SEA": "assets/logos/seattle.png",
    "TOR": "assets/logos/toronto.png",
    "VAN": "assets/logos/vancouver.png",
}

TEAM_FULL_NAMES = {
    "BOS": "Boston",   "MIN": "Minnesota", "MTL": "Montreal",
    "NYR": "New York", "OTT": "Ottawa",    "SEA": "Seattle",
    "TOR": "Toronto",  "VAN": "Vancouver",
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def logo_uri(abbr: str) -> str | None:
    path = TEAM_LOGOS.get(abbr, "")
    if path and Path(path).exists():
        return Path(path).resolve().as_uri()
    return None


def initials(name: str) -> str:
    parts = name.split()
    return "".join(p[0] for p in parts if p)[:2].upper()


# ── Event scoring (auto-pick) ─────────────────────────────────────────────────
EVENT_ICONS = {
    "HAT_TRICK":      "🎩",
    "MILESTONE":      "⭐",
    "POINT_STREAK":   "🔥",
    "SEASON_FIRST":   "👑",
    "CAREER_RECORD":  "🏒",
    "SHUTOUT":        "🧱",
    "COMEBACK_WIN":   "⚡",
}

EVENT_LABELS = {
    "HAT_TRICK":     "Hat Trick",
    "MILESTONE":     "Milestone",
    "POINT_STREAK":  "Point Streak",
    "SEASON_FIRST":  "Season First",
    "CAREER_RECORD": "Career Record",
    "SHUTOUT":       "Shutout",
    "COMEBACK_WIN":  "Comeback Win",
}

EVENT_PRIORITY = list(EVENT_ICONS.keys())  # priority order

def pick_event(flagged_events: list[dict]) -> dict:
    """
    Auto-pick the most significant event from your milestone detector output.
    flagged_events: list of dicts from your MilestoneDetector, each with:
      { type, player_name, player_team, player_position, stats, headline, body, ... }
    Returns the highest-priority event.
    """
    if not flagged_events:
        return None
    ranked = sorted(flagged_events, key=lambda e: EVENT_PRIORITY.index(e["type"])
                    if e["type"] in EVENT_PRIORITY else 99)
    e = ranked[0]
    e.setdefault("icon",        EVENT_ICONS.get(e["type"], "📊"))
    e.setdefault("type_label",  EVENT_LABELS.get(e["type"], e["type"].replace("_", " ").title()))
    e.setdefault("is_override", False)
    e.setdefault("player_photo",    None)
    e.setdefault("player_initials", initials(e.get("player_name", "??")))
    return e


def manual_override_event() -> dict:
    """Interactive CLI prompt for manual story override."""
    print("\n── Manual Event Override ──")
    player_name = input("Player name: ").strip()
    player_team = input("Team: ").strip()
    player_pos  = input("Position (e.g. F, D, G): ").strip()
    event_type  = input(f"Event type {list(EVENT_ICONS.keys())}: ").strip().upper()
    headline    = input("Headline (use <em>text</em> for purple highlights): ").strip()
    body        = input("Body text (1-2 sentences): ").strip()

    stats = []
    print("Enter up to 3 stats (label then value). Leave label blank to stop.")
    for _ in range(3):
        lbl = input("  Stat label: ").strip()
        if not lbl:
            break
        val = input("  Stat value: ").strip()
        stats.append({"label": lbl, "value": val})

    return {
        "type":             event_type,
        "icon":             EVENT_ICONS.get(event_type, "📊"),
        "type_label":       EVENT_LABELS.get(event_type, event_type.replace("_", " ").title()),
        "is_override":      True,
        "player_name":      player_name,
        "player_team":      player_team,
        "player_position":  player_pos,
        "player_photo":     None,
        "player_initials":  initials(player_name),
        "stats":            stats,
        "headline":         headline,
        "body":             body,
    }


# ── Sample data ───────────────────────────────────────────────────────────────
def get_sample_data() -> dict:
    games = [
        {"date_short": "MON 1/6", "home_abbr": "NYR", "away_abbr": "TOR",
         "home_team": "New York", "away_team": "Toronto",
         "home_score": 3, "away_score": 1, "result_type": "REG",
         "home_logo": logo_uri("NYR"), "away_logo": logo_uri("TOR")},
        {"date_short": "WED 1/8", "home_abbr": "SEA", "away_abbr": "MIN",
         "home_team": "Seattle", "away_team": "Minnesota",
         "home_score": 2, "away_score": 3, "result_type": "OT",
         "home_logo": logo_uri("SEA"), "away_logo": logo_uri("MIN")},
        {"date_short": "FRI 1/10", "home_abbr": "VAN", "away_abbr": "MTL",
         "home_team": "Vancouver", "away_team": "Montreal",
         "home_score": 4, "away_score": 2, "result_type": "REG",
         "home_logo": logo_uri("VAN"), "away_logo": logo_uri("MTL")},
        {"date_short": "SUN 1/12", "home_abbr": "OTT", "away_abbr": "BOS",
         "home_team": "Ottawa", "away_team": "Boston",
         "home_score": 1, "away_score": 2, "result_type": "SO",
         "home_logo": logo_uri("OTT"), "away_logo": logo_uri("BOS")},
    ]

    standings = [
        {"abbr": "MIN", "name": "Minnesota", "logo": logo_uri("MIN"),
         "gp": 22, "wins": 15, "losses": 5, "otw": 1, "otl": 1,
         "home_record": "8-2", "away_record": "7-3", "points": 47},
        {"abbr": "NYR", "name": "New York",  "logo": logo_uri("NYR"),
         "gp": 22, "wins": 13, "losses": 6, "otw": 2, "otl": 1,
         "home_record": "7-3", "away_record": "6-3", "points": 42},
        {"abbr": "BOS", "name": "Boston",    "logo": logo_uri("BOS"),
         "gp": 21, "wins": 12, "losses": 6, "otw": 1, "otl": 2,
         "home_record": "6-3", "away_record": "6-3", "points": 39},
        {"abbr": "TOR", "name": "Toronto",   "logo": logo_uri("TOR"),
         "gp": 22, "wins": 11, "losses": 8, "otw": 1, "otl": 2,
         "home_record": "6-4", "away_record": "5-4", "points": 36},
        {"abbr": "OTT", "name": "Ottawa",    "logo": logo_uri("OTT"),
         "gp": 21, "wins": 10, "losses": 8, "otw": 2, "otl": 1,
         "home_record": "5-4", "away_record": "5-4", "points": 35},
        {"abbr": "MTL", "name": "Montreal",  "logo": logo_uri("MTL"),
         "gp": 22, "wins": 9,  "losses": 10, "otw": 1, "otl": 2,
         "home_record": "5-5", "away_record": "4-5", "points": 31},
        {"abbr": "VAN", "name": "Vancouver", "logo": logo_uri("VAN"),
         "gp": 22, "wins": 7,  "losses": 12, "otw": 1, "otl": 2,
         "home_record": "4-6", "away_record": "3-6", "points": 25},
        {"abbr": "SEA", "name": "Seattle",   "logo": logo_uri("SEA"),
         "gp": 21, "wins": 5,  "losses": 14, "otw": 1, "otl": 1,
         "home_record": "3-7", "away_record": "2-7", "points": 19},
    ]

    event = pick_event([
        {
            "type":            "HAT_TRICK",
            "player_name":     "Marie-Philip Poulin",
            "player_team":     "Montreal",
            "player_position": "F",
            "player_photo":    None,
            "team_logo":       logo_uri("MTL"),
            "stats": [
                {"label": "Goals",   "value": "3"},
                {"label": "Assists", "value": "1"},
                {"label": "Points",  "value": "4"},
            ],
            "headline": '<em>Poulin</em> Lights the Lamp Three Times in Dominant Montreal Performance',
            "body": "Marie-Philip Poulin recorded her first hat trick of the season Friday night, "
                    "adding an assist for a 4-point game that moved Montreal within 4 points of the playoff line.",
        }
    ])

    # Teaser — auto-computed from games/standings, wire to DB later
    total_goals = sum(g["home_score"] + g["away_score"] for g in games)
    top_team    = standings[0]
    teaser = {
        "games_played": len(games),
        "stat_line":    f"<em>{total_goals}</em> goals scored",
        "leader_name":  top_team["name"],
        "leader_stat":  f"{top_team['points']} PTS",
    }

    return {
        "season":     "2025–26",
        "week_range": "JAN 6 – JAN 12",
        "week_end":   "JAN 12, 2026",
        "theme":      "light",
        "games":      games,
        "standings":  standings,
        "event":      event,
        "teaser":     teaser,
    }


# ── DB data (wire up your pipeline here) ─────────────────────────────────────
def get_db_data() -> dict:
    try:
        import sqlalchemy as sa
        DATABASE_URL = os.environ.get("PWHL_DATABASE_URL", "postgresql://localhost/pwhl")
        engine = sa.create_engine(DATABASE_URL)

        today      = datetime.today().date()
        week_start = today - timedelta(days=today.weekday() + 7)  # last Mon
        week_end   = week_start + timedelta(days=6)

        with engine.connect() as conn:
            # -- Scores
            game_rows = conn.execute(sa.text("""
                SELECT g.id, g.date, ht.abbreviation AS home_abbr,
                       at.abbreviation AS away_abbr,
                       g.home_score, g.away_score, g.result_type
                FROM games g
                JOIN teams ht ON g.home_team_id = ht.id
                JOIN teams at ON g.away_team_id = at.id
                WHERE g.date BETWEEN :start AND :end
                ORDER BY g.date
            """), {"start": week_start, "end": week_end}).fetchall()

            # -- Standings
            standing_rows = conn.execute(sa.text("""
                SELECT t.abbreviation, t.name,
                       COUNT(*) AS gp,
                       SUM(CASE WHEN g.winner_id = t.id AND g.result_type='REG' THEN 1 ELSE 0 END) AS wins,
                       SUM(CASE WHEN g.winner_id != t.id AND g.result_type='REG' THEN 1 ELSE 0 END) AS losses,
                       SUM(CASE WHEN g.winner_id = t.id AND g.result_type IN ('OT','SO') THEN 1 ELSE 0 END) AS otw,
                       SUM(CASE WHEN g.winner_id != t.id AND g.result_type IN ('OT','SO') THEN 1 ELSE 0 END) AS otl,
                       SUM(t.points_earned) AS points
                FROM teams t JOIN game_team_stats g ON g.team_id = t.id
                WHERE g.season_id = (SELECT id FROM seasons WHERE is_current = true)
                GROUP BY t.id, t.abbreviation, t.name
                ORDER BY points DESC
            """)).fetchall()

            # -- Flagged milestone events (from your MilestoneDetector output table)
            event_rows = conn.execute(sa.text("""
                SELECT * FROM milestone_events
                WHERE game_date BETWEEN :start AND :end
                ORDER BY priority_score DESC
                LIMIT 10
            """), {"start": week_start, "end": week_end}).fetchall()

        def fmt_date(d):
            return datetime.strptime(str(d), "%Y-%m-%d").strftime("%a %-m/%-d").upper()

        games = [{
            "date_short":  fmt_date(r.date),
            "home_abbr":   r.home_abbr,
            "away_abbr":   r.away_abbr,
            "home_team":   TEAM_FULL_NAMES.get(r.home_abbr, r.home_abbr),
            "away_team":   TEAM_FULL_NAMES.get(r.away_abbr, r.away_abbr),
            "home_score":  r.home_score,
            "away_score":  r.away_score,
            "result_type": r.result_type,
            "home_logo":   logo_uri(r.home_abbr),
            "away_logo":   logo_uri(r.away_abbr),
        } for r in game_rows]

        standings = [{
            "abbr":         r.abbreviation,
            "name":         TEAM_FULL_NAMES.get(r.abbreviation, r.name),
            "logo":         logo_uri(r.abbreviation),
            "gp":           r.gp,
            "wins":         r.wins,
            "losses":       r.losses,
            "otw":          r.otw,
            "otl":          r.otl,
            "home_record":  r.home_record,
            "away_record":  r.away_record,
            "points":       r.points,
        } for r in standing_rows]

        flagged = [dict(r._mapping) for r in event_rows]
        event   = pick_event(flagged) if flagged else get_sample_data()["event"]

        total_goals = sum(g["home_score"] + g["away_score"] for g in games)
        top_team    = standings[0] if standings else {}
        teaser = {
            "games_played": len(games),
            "stat_line":    f"<em>{total_goals}</em> goals scored",
            "leader_name":  top_team.get("name", "—"),
            "leader_stat":  f"{top_team.get('points', '—')} PTS",
        }

        return {
            "season":     "2025–26",
            "week_range": f"{week_start.strftime('%b %-d').upper()} – {week_end.strftime('%b %-d').upper()}",
            "week_end":   week_end.strftime("%b %-d, %Y").upper(),
            "theme":      "light",
            "games":      games,
            "standings":  standings,
            "event":      event,
            "teaser":     teaser,
        }

    except Exception as e:
        print(f"[DB ERROR] {e} — falling back to sample data")
        return get_sample_data()


# ── Renderer ──────────────────────────────────────────────────────────────────
def render_slide(template_name: str, data: dict, output_path: Path) -> Path:
    env  = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    tmpl = env.get_template(template_name)
    html = tmpl.render(**data)

    html_path = OUTPUT_DIR / f"_render_{template_name}"
    html_path.write_text(html, encoding="utf-8")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page    = browser.new_page(viewport={"width": 1080, "height": 1920})
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
    outputs   = []
    print(f"\n🎬 Rendering Weekly Recap — {data['week_range']}")
    for tmpl, fname in slides:
        path = out_dir / fname.replace(".png", f"_{timestamp}.png")
        render_slide(tmpl, data, path)
        outputs.append(path)
    print(f"\n✨ Done — {len(outputs)} slides saved to {out_dir}")
    return outputs


# ── CLI ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Render PWHL Weekly Recap (3 slides)")
    parser.add_argument("--from-db",        action="store_true")
    parser.add_argument("--theme",          default="light", choices=["light", "dark"])
    parser.add_argument("--override-event", action="store_true",
                        help="Manually specify the Story of the Week")
    parser.add_argument("--out-dir",        type=str, default=None)
    args = parser.parse_args()

    data        = get_db_data() if args.from_db else get_sample_data()
    data["theme"] = args.theme

    if args.override_event:
        data["event"] = manual_override_event()
        data["event"]["is_override"] = True

    out_dir = Path(args.out_dir) if args.out_dir else OUTPUT_DIR
    render_all(data, out_dir)


if __name__ == "__main__":
    main()
