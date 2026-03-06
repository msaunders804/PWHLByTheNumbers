"""
render_player_spotlight.py — Renders the Wednesday player spotlight slide.

Usage:
    python render_player_spotlight.py            # auto-pick from DB
    python render_player_spotlight.py --sample   # sample data (no DB)
"""

import argparse
import json
import os
import urllib.request
from datetime import datetime
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


# Stat maxes for progress bars
STAT_MAXES = {
    "goals":   25,
    "assists": 30,
    "points":  50,
    "shots":   120,
    "toi_sec": 25 * 60,
}

def _pct(value, key) -> int:
    mx = STAT_MAXES.get(key, 1)
    return min(int((value / mx) * 100), 100)



def _rank_num(rank_str: str) -> str:
    """Extract just the number from '#12 in league' -> '#12'"""
    return rank_str.split(" ")[0] if rank_str else "—"

def generate_fun_fact(player_name, team, nationality, goals, assists, points) -> str:
    """
    Generates a stats-grounded fun fact. Strictly prohibits biographical
    claims (college, hometown, etc.) that Claude cannot verify — those
    require a separate web search workflow outside this inline call.
    Focuses on what the numbers actually show this season.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return f"One of {team}'s key contributors this season with {points} points."

    try:
        system = (
            "You write short, punchy player facts for BTN, a PWHL analytics account. "
            "You may ONLY reference the stats provided — goals, assists, points, nationality. "
            "Do NOT include college, hometown, draft history, or any biographical detail "
            "not explicitly given to you. If you are tempted to add background, don't. "
            "Focus entirely on what the numbers show: scoring pace, consistency, impact."
        )
        prompt = (
            f"Write one engaging fact about {player_name} ({team}, {nationality}). "
            f"Season stats: {goals}G, {assists}A, {points}PTS. "
            f"1-2 sentences max. Conversational, no emojis, no quotes. "
            f"Do not start with her name. Only reference the stats above."
        )
        payload = json.dumps({
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 150,
            "system": system,
            "messages": [{"role": "user", "content": prompt}]
        }).encode()

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
                "x-api-key": api_key,
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())

        if data.get("stop_reason") == "max_tokens":
            print("  [Fun fact] Truncated — using fallback")
            return f"One of {team}'s key contributors this season with {points} points."

        text_blocks = [b["text"] for b in data["content"] if b.get("type") == "text"]
        if text_blocks:
            return text_blocks[-1].strip()

        return f"One of {team}'s key contributors this season with {points} points."

    except Exception as e:
        print(f"  [Fun fact] API error: {e}")
        return f"One of {team}'s key contributors this season with {points} points."


def get_sample_data() -> dict:
    goals, assists, points, shots = 8, 14, 22, 67
    toi_sec = 18 * 60 + 42
    return {
        "player_name":   "Sarah Nurse",
        "player_team":   "Vancouver Goldeneyes",
        "position":      "F",
        "jersey_number": "20",
        "nationality":   "CAN",
        "college":       "University of Wisconsin",
        "gp":            22,
        "goals":         goals,
        "assists":       assists,
        "points":        points,
        "shots":         shots,
        "toi":           "18:42",
        "goals_rank":    "#12 in league",
        "assists_rank":  "#8 in league",
        "points_rank":   "#9 in league",
        "shots_rank":    "#6 in league",
        "toi_rank":      "#11 in league",
        "goals_rank_num":   "#12",
        "assists_rank_num": "#8",
        "points_rank_num":  "#9",
        "shots_rank_num":   "#6",
        "toi_rank_num":     "#11",
        "goals_pct":     _pct(goals,   "goals"),
        "assists_pct":   _pct(assists, "assists"),
        "points_pct":    _pct(points,  "points"),
        "shots_pct":     _pct(shots,   "shots"),
        "toi_pct":       _pct(toi_sec, "toi_sec"),
        "fun_fact":      "A former basketball player, she chose hockey at age 10 after watching her cousins play — and hasn't looked back since.",
        "player_photo":  None,
        "pwhl_logo":     None,
        "season_label":  "Season 8",
    }


def get_db_data(player: str = None) -> dict | None:
    import sys
    sys.path.insert(0, str(BASE_DIR / "pwhl"))
    from db_queries import (get_spotlight_player,
                             get_spotlight_player_by_id,
                             get_spotlight_player_by_name)
    if player:
        # Try numeric ID first, then name match
        if player.isdigit():
            data = get_spotlight_player_by_id(int(player))
        else:
            data = get_spotlight_player_by_name(player)
        if not data:
            return None
    else:
        data = get_spotlight_player()
        if not data:
            print("  No eligible players — using sample data")
            return get_sample_data()

    toi_parts = data["toi"].split(":")
    toi_sec   = int(toi_parts[0]) * 60 + int(toi_parts[1])

    data["goals_pct"]    = _pct(data["goals"],   "goals")
    data["assists_pct"]  = _pct(data["assists"],  "assists")
    data["points_pct"]   = _pct(data["points"],   "points")
    data["shots_pct"]    = _pct(data["shots"],    "shots")
    data["toi_pct"]      = _pct(toi_sec,          "toi_sec")
    data["college"]      = data.get("college", "")
    if data.get("position") == "G":
        # Goalie — fetch goalie-specific stats
        import sys as _sys
        _sys.path.insert(0, str(BASE_DIR / "pwhl"))
        from db_queries import get_spotlight_goalie as _gsg
        from sqlalchemy import create_engine as _ce
        from sqlalchemy.orm import sessionmaker as _sm
        from db_config import get_db_url as _gdu
        _sess = _sm(bind=_ce(_gdu()))()
        goalie_stats = _gsg(data["player_id"], _sess)
        _sess.close()
        data.update(goalie_stats)
        data["_is_goalie"] = True
    else:
        data["goals_rank_num"]   = _rank_num(data["goals_rank"])
        data["assists_rank_num"] = _rank_num(data["assists_rank"])
        data["points_rank_num"]  = _rank_num(data["points_rank"])
        data["shots_rank_num"]   = _rank_num(data["shots_rank"])
        data["toi_rank_num"]     = _rank_num(data["toi_rank"])
        data["_is_goalie"] = False
    data["season_label"] = "Season 8"

    print(f"  Generating fun fact for {data['player_name']}...")
    data["fun_fact"] = generate_fun_fact(
        data["player_name"], data["player_team"], data["nationality"],
        data["goals"], data["assists"], data["points"]
    )
    return data


def render_spotlight(data: dict, output_path: Path) -> Path:
    env           = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template_name = "goalie_spotlight.html" if data.get("_is_goalie") else "player_spotlight.html"
    template      = env.get_template(template_name)
    html     = template.render(**data)
    tmp_html = OUTPUT_DIR / "_render_spotlight.html"
    tmp_html.write_text(html, encoding="utf-8")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page    = browser.new_page(viewport={"width": 1080, "height": 1920})
        page.goto(f"file://{tmp_html.resolve()}")
        page.wait_for_timeout(800)
        page.screenshot(path=str(output_path), clip={"x": 0, "y": 0, "width": 1080, "height": 1920})
        browser.close()
    print(f"  ✅ {output_path.name}")
    return output_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", action="store_true")
    parser.add_argument("--player", type=str, default=None,
                        help="Player name (partial match) or numeric ID to spotlight")
    args      = parser.parse_args()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    out_path  = OUTPUT_DIR / f"spotlight_{timestamp}.png"

    if args.sample:
        data = get_sample_data()
    elif args.player:
        data = get_db_data(player=args.player)
        if data is None:
            print(f"  No player found matching \'{args.player}\'")
            return None
    else:
        data = get_db_data()

    print(f"\nRendering spotlight: {data['player_name']} ({data['player_team']})")
    render_spotlight(data, out_path)
    print(f"  Saved to {out_path}")
    return out_path


if __name__ == "__main__":
    main()
