"""
goalie_tiktok_render.py — Render the 4-slide goalie TikTok graphic set.

Slides:
  0 — Hook         GSAA leaderboard table
  1 — Game Log     Phillips' game log with Apr 11 highlighted
  2 — Stolen Games Kirk's stolen games list
  3 — Close        Full standings with goalie GSAA column

Usage:
    from pwhl_btn.render.goalie_tiktok_render import render_goalie_tiktok
    paths = render_goalie_tiktok()

    python -m pwhl_btn.render.goalie_tiktok_render
"""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

from pwhl_btn.analytics.gsaa import (
    get_season_gsaa,
    get_goalie_game_log,
    get_stolen_games,
    SEASON_ID,
)
from pwhl_btn.db.db_queries import get_clinch_data

TEMPLATE_DIR = Path(__file__).parent / "templates"
OUTPUT_DIR   = Path(__file__).parent / "output"

# Player IDs — update if needed
PHILLIPS_ID = 222
KIRK_ID     = None   # resolved at runtime from leaderboard

HIGHLIGHT_DATE = "Apr 11"   # fragment matched against date_str


def _fmt_pct(v) -> str:
    return f".{int(round(float(v or 0), 3) * 1000):03d}"


def _fmt_gsaa(v) -> str:
    return f"{float(v):+.2f}"


def _build_hook_data(leaderboard: list[dict]) -> dict:
    goalies = []
    for g in leaderboard:
        gsaa_raw = float(g["gsaa"])
        goalies.append({
            "name":      g["name"],
            "team_code": g["team_code"],
            "gp":        int(g["gp"]),
            "sv_pct":    _fmt_pct(g["sv_pct"]),
            "gaa":       f"{float(g['gaa'] or 0):.2f}",
            "wins":      int(g["wins"]),
            "gsaa":      _fmt_gsaa(gsaa_raw),
            "gsaa_raw":  gsaa_raw,
            "highlight": g["team_code"] in ("OTT", "TOR"),  # Phillips / Kirk teams
        })
    return {"goalies": goalies}


def _build_gamelog_data(player_id: int, leaderboard: list[dict]) -> dict:
    game_log_raw = get_goalie_game_log(player_id)
    season_row   = next((g for g in leaderboard if g["player_id"] == player_id), {})

    game_log = []
    for g in game_log_raw:
        sv_raw   = float(g.get("game_sv_pct") or 0)
        gsaa_val = float(g["gsaa"])
        game_log.append({
            **g,
            "sv_pct_fmt": _fmt_pct(sv_raw),
            "gsaa_fmt":   _fmt_gsaa(gsaa_val),
            "highlighted": HIGHLIGHT_DATE.lower() in g.get("date_str", "").lower(),
        })

    return {
        "player_name": season_row.get("name", "Gwyneth Phillips"),
        "team_code":   season_row.get("team_code", "OTT"),
        "sv_pct":      _fmt_pct(season_row.get("sv_pct")),
        "gaa":         f"{float(season_row.get('gaa') or 0):.2f}",
        "wins":        int(season_row.get("wins", 0)),
        "season_gsaa": _fmt_gsaa(float(season_row.get("gsaa", 0))),
        "game_log":    game_log,
    }


def _build_stolen_data(player_id: int, leaderboard: list[dict]) -> dict:
    stolen_raw = get_stolen_games(player_id)
    season_row = next((g for g in leaderboard if g["player_id"] == player_id), {})

    stolen = []
    for g in stolen_raw:
        shots_above = round(float(g["shots_against"]) - g["team_avg_sa"], 1)
        stolen.append({
            **g,
            "sv_pct_fmt":   _fmt_pct(float(g.get("game_sv_pct") or 0)),
            "gsaa_fmt":     _fmt_gsaa(float(g["gsaa"])),
            "shots_above":  f"+{shots_above:.1f}" if shots_above >= 0 else f"{shots_above:.1f}",
            "result_type":  g.get("result_type") or "REG",
        })

    return {
        "player_name":  season_row.get("name", "Raygan Kirk"),
        "team_code":    season_row.get("team_code", "TOR"),
        "stolen_count": len(stolen),
        "stolen_games": stolen,
    }


def _build_close_data(leaderboard: list[dict]) -> dict:
    # Build GSAA map keyed by team_code
    gsaa_by_team: dict[str, float] = {}
    for g in leaderboard:
        code = g["team_code"]
        val  = float(g["gsaa"])
        if code not in gsaa_by_team or val > gsaa_by_team[code]:
            gsaa_by_team[code] = val

    # Compute standings from results view via db_queries
    from pwhl_btn.db.db_config import get_engine
    from sqlalchemy import text

    engine = get_engine(pool_pre_ping=True)
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT t.team_id, t.team_code, t.team_name,
                   COUNT(DISTINCT g.game_id) AS gp,
                   SUM(CASE
                       WHEN g.result_type = 'REG'
                        AND ((g.home_team_id = t.team_id AND g.home_score > g.away_score) OR
                             (g.away_team_id = t.team_id AND g.away_score > g.home_score))
                       THEN 3
                       WHEN g.result_type IN ('OT','SO')
                        AND ((g.home_team_id = t.team_id AND g.home_score > g.away_score) OR
                             (g.away_team_id = t.team_id AND g.away_score > g.home_score))
                       THEN 2
                       WHEN g.result_type IN ('OT','SO')
                        AND ((g.home_team_id = t.team_id AND g.home_score < g.away_score) OR
                             (g.away_team_id = t.team_id AND g.away_score < g.home_score))
                       THEN 1
                       ELSE 0 END)                             AS pts,
                   SUM(CASE
                       WHEN (g.home_team_id = t.team_id AND g.home_score > g.away_score) OR
                            (g.away_team_id = t.team_id AND g.away_score > g.home_score)
                       THEN 1 ELSE 0 END)                     AS wins,
                   SUM(CASE
                       WHEN g.result_type = 'REG'
                        AND ((g.home_team_id = t.team_id AND g.home_score < g.away_score) OR
                             (g.away_team_id = t.team_id AND g.away_score < g.home_score))
                       THEN 1 ELSE 0 END)                     AS losses,
                   SUM(CASE
                       WHEN g.result_type IN ('OT','SO')
                        AND ((g.home_team_id = t.team_id AND g.home_score < g.away_score) OR
                             (g.away_team_id = t.team_id AND g.away_score < g.home_score))
                       THEN 1 ELSE 0 END)                     AS otl
            FROM teams t
            LEFT JOIN games g ON (g.home_team_id = t.team_id OR g.away_team_id = t.team_id)
                              AND g.season_id = :sid AND g.game_status = 'final'
            WHERE t.season_id = :sid
            GROUP BY t.team_id, t.team_code, t.team_name
            ORDER BY pts DESC, wins DESC
        """), {"sid": SEASON_ID}).fetchall()

    standings = []
    for i, r in enumerate(rows):
        code     = r.team_code
        gsaa_raw = gsaa_by_team.get(code, 0.0)
        if i < 4:
            status = "in"
        elif i == 4:
            status = "bubble"
        else:
            status = "out"
        standings.append({
            "team_code":     code,
            "team_name":     r.team_name,
            "gp":            int(r.gp),
            "wins":          int(r.wins or 0),
            "losses":        int(r.losses or 0),
            "otl":           int(r.otl or 0),
            "pts":           int(r.pts or 0),
            "goalie_gsaa":   _fmt_gsaa(gsaa_raw),
            "goalie_gsaa_raw": gsaa_raw,
            "playoff_status": status,
        })

    return {"standings": standings}


def render_goalie_tiktok(
    phillips_id: int = PHILLIPS_ID,
    kirk_id: int | None = KIRK_ID,
    out_dir: Path | None = None,
) -> list[Path]:
    """
    Render all 4 goalie TikTok slides.

    Args:
        phillips_id: player_id for Gwyneth Phillips (game log slide).
        kirk_id:     player_id for Raygan Kirk (stolen games slide).
                     If None, resolved from the leaderboard by team_code 'TOR'.
        out_dir:     Output directory (defaults to render/output/).

    Returns:
        List of 4 Paths to generated PNGs in slide order.
    """
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    print("\n── Goalie TikTok Render ─────────────────────────────────────────")
    print("  Loading leaderboard…")
    leaderboard = get_season_gsaa()
    if not leaderboard:
        raise RuntimeError("No qualified goalies found — is goalie_game_stats populated?")

    # Resolve Kirk's player_id if not supplied
    resolved_kirk_id = kirk_id
    if resolved_kirk_id is None:
        match = next((g for g in leaderboard if g["team_code"] == "TOR"), None)
        if not match:
            raise RuntimeError("Could not find a TOR goalie in the leaderboard.")
        resolved_kirk_id = match["player_id"]
        print(f"  Resolved Kirk player_id={resolved_kirk_id} ({match['name']})")

    print("  Building slide data…")
    slides_data = [
        ("goalie_tiktok_hook.html",   "hook",          _build_hook_data(leaderboard)),
        ("goalie_tiktok_stolen.html", "stolen_phillips", _build_stolen_data(phillips_id, leaderboard)),
        ("goalie_tiktok_stolen.html", "stolen_kirk",     _build_stolen_data(resolved_kirk_id, leaderboard)),
        ("goalie_tiktok_close.html",  "close",          _build_close_data(leaderboard)),
    ]

    env     = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    outputs: list[Path] = []

    print(f"\n  Rendering {len(slides_data)} slides…")
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for tmpl_name, label, data in slides_data:
            tmpl      = env.get_template(tmpl_name)
            html      = tmpl.render(**data)
            html_path = out_dir / f"_render_goalie_tiktok_{label}.html"
            html_path.write_text(html, encoding="utf-8")

            out_path = out_dir / f"goalie_tiktok_{label}.png"
            page     = browser.new_page(viewport={"width": 1080, "height": 1920})
            page.goto(f"file://{html_path.resolve()}")
            page.wait_for_timeout(900)
            page.screenshot(path=str(out_path), full_page=False)
            page.close()
            html_path.unlink(missing_ok=True)
            print(f"  ✅ {out_path.name}")
            outputs.append(out_path)
        browser.close()

    print(f"\n✨ Done — {len(outputs)} slides saved to {out_dir}")
    return outputs


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Render goalie TikTok slides")
    parser.add_argument("--phillips-id", type=int, default=PHILLIPS_ID,
                        help=f"player_id for Phillips (default {PHILLIPS_ID})")
    parser.add_argument("--kirk-id", type=int, default=None,
                        help="player_id for Kirk (auto-resolved from TOR if omitted)")
    args = parser.parse_args()
    render_goalie_tiktok(phillips_id=args.phillips_id, kirk_id=args.kirk_id)
