"""
render_power_rankings.py — Thursday power rankings post (2 slides).

Usage:
    python render_power_rankings.py            # live data from DB
    python render_power_rankings.py --sample   # sample data (no DB)
    python render_power_rankings.py --skip-drive
"""

import argparse
import json
import os
import urllib.request
from datetime import datetime, date
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


def _week_label() -> str:
    today = date.today()
    return today.strftime("%B %d, %Y").upper()


def _generate_blurbs(rankings: list[dict]) -> list[dict]:
    """
    Call Claude to generate a short opinionated blurb for each team.
    Falls back to a data-driven default if API call fails.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        for team in rankings:
            team["blurb"] = _default_blurb(team)
        return rankings

    teams_summary = "\n".join(
        f"#{t['rank']} {t['team_code']}: streak={t['streak_label']}, "
        f"PPG={t['ppg']:.2f}, last5_gd={t['last5_gd']:+d}, pts={t['pts']}"
        for t in rankings
    )

    prompt = f"""You are the analyst behind BTN (By The Numbers), a PWHL analytics account.
Write a SHORT, punchy, opinionated one-liner for each team's power ranking position.
Be bold — fans should agree or disagree strongly. Max 7 words per blurb.
Focus on current streak and recent form above all else.
Return ONLY a JSON array of 8 strings in ranking order (no keys, no markdown).

Current rankings:
{teams_summary}"""

    try:
        body = json.dumps({
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 400,
            "messages": [{"role": "user", "content": prompt}]
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            }
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
        text = data["content"][0]["text"].strip()
        # Strip markdown fences if present
        text = text.replace("```json", "").replace("```", "").strip()
        blurbs = json.loads(text)
        for i, team in enumerate(rankings):
            team["blurb"] = blurbs[i] if i < len(blurbs) else _default_blurb(team)
    except Exception as e:
        print(f"  [Blurbs] Claude API error: {e} — using defaults")
        for team in rankings:
            team["blurb"] = _default_blurb(team)

    return rankings


def _generate_hot_player_blurb(player: dict) -> str:
    """Generate an opinionated sentence about the hot player."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return _default_hot_player_blurb(player)

    prompt = (
        f"You write for BTN (By The Numbers), a bold PWHL analytics account. "
        f"Write ONE punchy sentence (max 20 words) about why {player['player_name']} "
        f"is the hottest player right now. "
        f"Stats: {player['last5_pts']} pts in last 5 games "
        f"({player['last5_goals']}G, {player['last5_assists']}A), "
        f"#{'1' if player.get('pts_rank') == 1 else str(player.get('pts_rank',''))} in league scoring "
        f"with {player['season_pts']} season points. "
        f"Be opinionated and specific. Return ONLY the sentence, no quotes."
    )
    try:
        body = json.dumps({
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 80,
            "messages": [{"role": "user", "content": prompt}]
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            }
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
        return data["content"][0]["text"].strip().strip('"')
    except Exception as e:
        print(f"  [Blurb] {e}")
        return _default_hot_player_blurb(player)


def _default_hot_player_blurb(player: dict) -> str:
    g, a = player["last5_goals"], player["last5_assists"]
    if g >= 4:
        return f"A goal-scoring machine — {g} in her last 5 games, impossible to stop."
    elif a >= 5:
        return f"Making everyone around her better. {a} assists in 5 games is ridiculous."
    else:
        return f"{player['last5_pts']} points in 5 games. She is running the league right now."


def _default_blurb(team: dict) -> str:
    s = team["streak"]
    gd = team["last5_gd"]
    if s >= 4:
        return f"Nobody stopping them right now"
    elif s >= 2:
        return f"Finding their rhythm"
    elif s <= -4:
        return f"Alarm bells ringing"
    elif s <= -2:
        return f"Needs to turn it around fast"
    elif gd >= 5:
        return f"Outscoring everyone lately"
    elif gd <= -5:
        return f"Leaking goals at the wrong time"
    else:
        return f"Treading water"


def get_sample_data() -> dict:
    rankings = [
        {"rank": 1, "team_code": "MTL", "logo": None, "gp": 29, "pts": 39, "ppg": 1.34,
         "season_gd": 18, "last5_gd": 8, "last5_wins": 4, "streak": 5,
         "streak_label": "W5", "streak_hot": True, "streak_cold": False,
         "blurb": "Nobody stopping them right now"},
        {"rank": 2, "team_code": "BOS", "logo": None, "gp": 28, "pts": 36, "ppg": 1.29,
         "season_gd": 12, "last5_gd": 4, "last5_wins": 3, "streak": 3,
         "streak_label": "W3", "streak_hot": True, "streak_cold": False,
         "blurb": "Quietly building something special"},
        {"rank": 3, "team_code": "MIN", "logo": None, "gp": 29, "pts": 34, "ppg": 1.17,
         "season_gd": 6, "last5_gd": 2, "last5_wins": 3, "streak": 2,
         "streak_label": "W2", "streak_hot": False, "streak_cold": False,
         "blurb": "Consistent but not dangerous"},
        {"rank": 4, "team_code": "TOR", "logo": None, "gp": 29, "pts": 32, "ppg": 1.10,
         "season_gd": 3, "last5_gd": -1, "last5_wins": 2, "streak": 1,
         "streak_label": "W1", "streak_hot": False, "streak_cold": False,
         "blurb": "Hanging on to fourth"},
        {"rank": 5, "team_code": "OTT", "logo": None, "gp": 29, "pts": 30, "ppg": 1.03,
         "season_gd": -2, "last5_gd": -3, "last5_wins": 2, "streak": -1,
         "streak_label": "L1", "streak_hot": False, "streak_cold": False,
         "blurb": "Bubble life is stressful"},
        {"rank": 6, "team_code": "NY", "logo": None, "gp": 28, "pts": 27, "ppg": 0.96,
         "season_gd": -5, "last5_gd": -2, "last5_wins": 1, "streak": -2,
         "streak_label": "L2", "streak_hot": False, "streak_cold": False,
         "blurb": "Fading at the wrong time"},
        {"rank": 7, "team_code": "VAN", "logo": None, "gp": 29, "pts": 22, "ppg": 0.76,
         "season_gd": -14, "last5_gd": -5, "last5_wins": 1, "streak": -3,
         "streak_label": "L3", "streak_hot": False, "streak_cold": True,
         "blurb": "Season slipping away"},
        {"rank": 8, "team_code": "SEA", "logo": None, "gp": 28, "pts": 17, "ppg": 0.61,
         "season_gd": -18, "last5_gd": -7, "last5_wins": 0, "streak": -5,
         "streak_label": "L5", "streak_hot": False, "streak_cold": True,
         "blurb": "Rough stretch, need a reset"},
    ]

    hot   = max(rankings, key=lambda x: x["streak"])
    cold  = min(rankings, key=lambda x: x["streak"])

    hot_player = {
        "player_id":      999,
        "player_name":    "Marie-Philip Poulin",
        "team_code":      "MTL",
        "team_name":      "Montréal",
        "team_logo":      None,
        "position":       "F",
        "jersey_number":  "29",
        "player_photo":   "https://assets.leaguestat.com/pwhl/240x240/463.jpg",
        "last5_pts":      8,
        "last5_goals":    4,
        "last5_assists":  4,
        "season_goals":   14,
        "season_assists": 18,
        "season_pts":     32,
        "season_gp":      29,
        "pts_rank":       1,
        "toi":            "19:42",
        "blurb":          "Four points in her last two games. She is simply operating on a different level right now.",
        "pwhl_logo":      None,
    }
    breakdown = {
        "teams": [
            {"team_code":"MTL","logo":None,"gp":29,"gf":74,"ga":47,"gfpg":2.55,"gapg":1.62,"archetype":"ELITE",      "archetype_color":"#5e17eb"},
            {"team_code":"BOS","logo":None,"gp":28,"gf":70,"ga":52,"gfpg":2.50,"gapg":1.86,"archetype":"ELITE",      "archetype_color":"#5e17eb"},
            {"team_code":"MIN","logo":None,"gp":29,"gf":65,"ga":58,"gfpg":2.24,"gapg":2.00,"archetype":"OFFENSIVE",  "archetype_color":"#f5a623"},
            {"team_code":"TOR","logo":None,"gp":29,"gf":58,"ga":54,"gfpg":2.00,"gapg":1.86,"archetype":"DEFENSIVE",  "archetype_color":"#2a9d3a"},
            {"team_code":"OTT","logo":None,"gp":29,"gf":60,"ga":63,"gfpg":2.07,"gapg":2.17,"archetype":"OFFENSIVE",  "archetype_color":"#f5a623"},
            {"team_code":"NY", "logo":None,"gp":28,"gf":52,"ga":60,"gfpg":1.86,"gapg":2.14,"archetype":"STRUGGLING", "archetype_color":"#c0392b"},
            {"team_code":"VAN","logo":None,"gp":29,"gf":48,"ga":71,"gfpg":1.66,"gapg":2.45,"archetype":"STRUGGLING", "archetype_color":"#c0392b"},
            {"team_code":"SEA","logo":None,"gp":28,"gf":43,"ga":66,"gfpg":1.54,"gapg":2.36,"archetype":"STRUGGLING", "archetype_color":"#c0392b"},
        ],
        "avg_gfpg": 2.05,
        "avg_gapg": 2.06,
    }
    return {
        "rankings":    rankings,
        "week_label":  _week_label(),
        "top_team":    rankings[0]["team_code"],
        "hot_team":    hot["team_code"],
        "hot_streak":  hot["streak_label"],
        "cold_team":   cold["team_code"],
        "cold_streak": cold["streak_label"],
        "pwhl_logo":   None,
        "hot_player":  hot_player,
        "breakdown":   breakdown,
        "season":      8,
    }


def get_live_data() -> dict:
    from db_queries import get_power_rankings, get_hot_player, get_offense_defense_breakdown, _pwhl_logo_uri

    rankings = get_power_rankings()
    rankings = _generate_blurbs(rankings)

    hot  = max(rankings, key=lambda x: x["streak"])
    cold = min(rankings, key=lambda x: x["streak"])

    hot_player = get_hot_player()
    if hot_player:
        hot_player["blurb"] = _generate_hot_player_blurb(hot_player)
        hot_player["pwhl_logo"] = _pwhl_logo_uri()

    breakdown = get_offense_defense_breakdown()

    return {
        "rankings":    rankings,
        "week_label":  _week_label(),
        "top_team":    rankings[0]["team_code"],
        "hot_team":    hot["team_code"],
        "hot_streak":  hot["streak_label"],
        "cold_team":   cold["team_code"],
        "cold_streak": cold["streak_label"],
        "pwhl_logo":   _pwhl_logo_uri(),
        "hot_player":  hot_player,
        "breakdown":   breakdown,
        "season":      8,
    }



def _build_scatter_svg(breakdown: dict) -> str:
    """
    Renders an SVG scatter plot: x=GFPG (right=better), y=GAPG (down=worse).
    Returns an SVG string to embed directly in the template.
    """
    teams    = breakdown["teams"]
    avg_gfpg = breakdown["avg_gfpg"]
    avg_gapg = breakdown["avg_gapg"]

    # Chart canvas dimensions (fits inside .chart-wrap)
    W, H   = 952, 980
    PAD    = dict(top=60, right=40, bottom=80, left=80)
    cw     = W - PAD["left"] - PAD["right"]
    ch     = H - PAD["top"]  - PAD["bottom"]

    # Data range with padding
    all_gf = [t["gfpg"] for t in teams]
    all_ga = [t["gapg"] for t in teams]
    gf_min = min(all_gf) - 0.25;  gf_max = max(all_gf) + 0.25
    ga_min = min(all_ga) - 0.25;  ga_max = max(all_ga) + 0.25

    def px(gfpg): return PAD["left"] + (gfpg - gf_min) / (gf_max - gf_min) * cw
    def py(gapg): return PAD["top"]  + (gapg - ga_min) / (ga_max - ga_min) * ch

    qx = px(avg_gfpg)  # vertical divider
    qy = py(avg_gapg)  # horizontal divider

    quad_colors = {
        "ELITE":      "#5e17eb",
        "OFFENSIVE":  "#f5a623",
        "DEFENSIVE":  "#2a9d3a",
        "STRUGGLING": "#c0392b",
    }

    lines = [f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">''']

    # Quadrant fills
    quads = [
        (PAD["left"], PAD["top"],         qx-PAD["left"],  qy-PAD["top"],   "ELITE"),
        (qx,          PAD["top"],         W-PAD["right"]-qx, qy-PAD["top"], "OFFENSIVE"),
        (PAD["left"], qy,                 qx-PAD["left"],  H-PAD["bottom"]-qy, "DEFENSIVE"),
        (qx,          qy,                 W-PAD["right"]-qx, H-PAD["bottom"]-qy, "STRUGGLING"),
    ]
    for x, y, w, h, arch in quads:
        col = quad_colors[arch]
        lines.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{col}" opacity="0.06"/>')

    # Quadrant archetype labels (corners)
    label_pos = [
        (PAD["left"]+16, PAD["top"]+32,  "ELITE",      "start",  "#5e17eb"),
        (W-PAD["right"]-16, PAD["top"]+32, "OFFENSIVE", "end",   "#f5a623"),
        (PAD["left"]+16, H-PAD["bottom"]-16, "DEFENSIVE","start","#2a9d3a"),
        (W-PAD["right"]-16, H-PAD["bottom"]-16,"STRUGGLING","end","#c0392b"),
    ]
    for lx, ly, txt, anchor, col in label_pos:
        lines.append(f'<text x="{lx}" y="{ly}" font-family="Bebas Neue,sans-serif" font-size="28" fill="{col}" opacity="0.55" text-anchor="{anchor}">{txt}</text>')

    # Grid lines
    for i in range(4):
        gx = PAD["left"] + cw * i / 3
        lines.append(f'<line x1="{gx:.1f}" y1="{PAD["top"]}" x2="{gx:.1f}" y2="{H-PAD["bottom"]}" stroke="rgba(0,0,0,0.07)" stroke-width="1"/>')
    for i in range(4):
        gy = PAD["top"] + ch * i / 3
        lines.append(f'<line x1="{PAD["left"]}" y1="{gy:.1f}" x2="{W-PAD["right"]}" y2="{gy:.1f}" stroke="rgba(0,0,0,0.07)" stroke-width="1"/>')

    # Quadrant dividers
    lines.append(f'<line x1="{qx:.1f}" y1="{PAD["top"]}" x2="{qx:.1f}" y2="{H-PAD["bottom"]}" stroke="rgba(0,0,0,0.25)" stroke-width="2" stroke-dasharray="8,5"/>')
    lines.append(f'<line x1="{PAD["left"]}" y1="{qy:.1f}" x2="{W-PAD["right"]}" y2="{qy:.1f}" stroke="rgba(0,0,0,0.25)" stroke-width="2" stroke-dasharray="8,5"/>')

    # Axis labels
    lines.append(f'<text x="{W//2}" y="{H-18}" font-family="Barlow Condensed,sans-serif" font-size="22" font-weight="700" fill="rgba(0,0,0,0.35)" text-anchor="middle" letter-spacing="3">GOALS FOR / GAME →</text>')
    lines.append(f'<text x="22" y="{H//2}" font-family="Barlow Condensed,sans-serif" font-size="22" font-weight="700" fill="rgba(0,0,0,0.35)" text-anchor="middle" letter-spacing="3" transform="rotate(-90,22,{H//2})">← GOALS AGAINST / GAME</text>')

    # Axis tick values
    for i in range(5):
        gf_val = gf_min + (gf_max - gf_min) * i / 4
        tx = PAD["left"] + cw * i / 4
        lines.append(f'<text x="{tx:.1f}" y="{H-PAD["bottom"]+22}" font-family="Barlow Condensed,sans-serif" font-size="18" fill="rgba(0,0,0,0.3)" text-anchor="middle">{gf_val:.1f}</text>')
    for i in range(5):
        ga_val = ga_min + (ga_max - ga_min) * i / 4
        ty = PAD["top"] + ch * i / 4
        lines.append(f'<text x="{PAD["left"]-10}" y="{ty+6:.1f}" font-family="Barlow Condensed,sans-serif" font-size="18" fill="rgba(0,0,0,0.3)" text-anchor="end">{ga_val:.1f}</text>')

    # Team chips
    R = 34  # chip radius
    for t in teams:
        cx_ = px(t["gfpg"])
        cy_ = py(t["gapg"])
        col = quad_colors[t["archetype"]]
        code = t["team_code"]

        if t["logo"]:
            # White circle + logo image
            lines.append(f'<circle cx="{cx_:.1f}" cy="{cy_:.1f}" r="{R+3}" fill="white" stroke="{col}" stroke-width="3"/>')
            lines.append(f'<image href="{t["logo"]}" x="{cx_-R:.1f}" y="{cy_-R:.1f}" width="{R*2}" height="{R*2}" clip-path="circle()"/>')
        else:
            # Fallback: filled circle with abbr
            lines.append(f'<circle cx="{cx_:.1f}" cy="{cy_:.1f}" r="{R+3}" fill="{col}" opacity="0.15" stroke="{col}" stroke-width="3"/>')
            lines.append(f'<text x="{cx_:.1f}" y="{cy_+10:.1f}" font-family="Bebas Neue,sans-serif" font-size="22" fill="{col}" text-anchor="middle">{code}</text>')

        # Stat label below chip
        stat = f"{t['gfpg']:.2f} / {t['gapg']:.2f}"
        lines.append(f'<text x="{cx_:.1f}" y="{cy_+R+20:.1f}" font-family="Barlow Condensed,sans-serif" font-size="16" fill="rgba(0,0,0,0.45)" text-anchor="middle" font-weight="700">{stat}</text>')

    lines.append("</svg>")
    return "\n".join(lines)


def render_slides(data: dict) -> list:
    env       = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    outputs   = []

    slides = [
        ("rankings_slide0.html", "hook"),
        ("rankings_slide1.html", "breakdown"),
        ("rankings_slide2.html", "hotplayer"),
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for tmpl_name, label in slides:
            template = env.get_template(tmpl_name)
            ctx = dict(data)
            if label == "breakdown" and data.get("breakdown"):
                ctx["chart_svg"] = _build_scatter_svg(data["breakdown"])
            if label == "hotplayer" and data.get("hot_player"):
                ctx.update(data["hot_player"])
            html = template.render(**ctx)
            out_path = OUTPUT_DIR / f"rankings_{label}_{timestamp}.png"
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

    print("\n── Power Rankings ──────────────────────────────")
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
