"""
run_ott_transformation.py — Ottawa Charge regular season vs playoff stat comparison.
Pulls SA, SF, SV% from DB and renders the transformation slide.
Usage: python -m pwhl_btn.jobs.run_ott_transformation
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright
from sqlalchemy import text
from sqlalchemy.orm import Session

from pwhl_btn.db.db_config import get_engine
from pwhl_btn.db.db_queries import _logo_uri, _file_to_data_uri, PLAYERS_DIR

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "render" / "templates"
OUTPUT_DIR   = Path(__file__).resolve().parents[3] / "src" / "pwhl_btn" / "render" / "output"

OTT_TEAM_ID = 5  # consistent across Season 8 and Season 9

engine = get_engine(pool_pre_ping=True)


def _load_stats(season_id: int) -> dict:
    with Session(engine) as s:
        goalie = s.execute(text("""
            SELECT COUNT(DISTINCT games.game_id) gp,
                   SUM(ggs.shots_against)        sa,
                   SUM(ggs.saves)                saves,
                   SUM(ggs.goals_against)        ga
            FROM games
            JOIN goalie_game_stats ggs
              ON ggs.game_id = games.game_id AND ggs.team_id = :tid
            WHERE games.season_id = :sid AND games.game_status = 'final'
        """), {"tid": OTT_TEAM_ID, "sid": season_id}).fetchone()

        skater = s.execute(text("""
            SELECT SUM(pgs.shots) sf
            FROM games
            JOIN player_game_stats pgs
              ON pgs.game_id = games.game_id AND pgs.team_id = :tid
            WHERE games.season_id = :sid AND games.game_status = 'final'
        """), {"tid": OTT_TEAM_ID, "sid": season_id}).fetchone()

        scores = s.execute(text("""
            SELECT COUNT(*) gp,
                   SUM(CASE WHEN g.home_team_id=:tid THEN g.home_score ELSE g.away_score END) gf,
                   SUM(CASE WHEN g.home_team_id=:tid THEN g.away_score ELSE g.home_score END) ga
            FROM games g
            WHERE g.season_id=:sid AND g.game_status='final'
              AND (g.home_team_id=:tid OR g.away_team_id=:tid)
        """), {"tid": OTT_TEAM_ID, "sid": season_id}).fetchone()

    gp        = goalie[0]
    sa        = goalie[1]
    saves     = goalie[2]
    shots_for = skater[0]
    gf        = scores[1]
    ga        = scores[2]

    return {
        "gp":     gp,
        "sa_pg":  sa / gp,
        "sf_pg":  shots_for / gp,
        "sv_pct": saves / sa,
        "gf_pg":  gf / gp,
        "ga_pg":  ga / gp,
        "ga_tot": ga,
    }


def _render(data: dict, slug: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    env  = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    html = env.get_template("ott_transformation.html").render(**data)

    html_path = out_dir / f"_render_{slug}.html"
    html_path.write_text(html, encoding="utf-8")
    out_path = out_dir / f"{slug}.png"

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1920})
        page.goto(f"file://{html_path.resolve()}")
        page.wait_for_timeout(1500)
        page.screenshot(path=str(out_path), full_page=False)
        browser.close()

    html_path.unlink(missing_ok=True)
    print(f"  [ok] {out_path.name}")
    return out_path


def run(out_dir: Path | None = None) -> None:
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR

    print("\n=== Ottawa Charge: Regular Season vs Playoffs ===")

    reg  = _load_stats(season_id=8)
    play = _load_stats(season_id=9)

    print(f"  Regular season ({reg['gp']} GP): SF/GP={reg['sf_pg']:.1f}  GF/GP={reg['gf_pg']:.2f}  SA/GP={reg['sa_pg']:.1f}  GA/GP={reg['ga_pg']:.2f}  SV%={reg['sv_pct']:.4f}")
    print(f"  Playoffs       ({play['gp']} GP): SF/GP={play['sf_pg']:.1f}  GF/GP={play['gf_pg']:.2f}  SA/GP={play['sa_pg']:.1f}  GA/GP={play['ga_pg']:.2f}  SV%={play['sv_pct']:.4f}")

    sa_pct_change = round((play["sa_pg"] - reg["sa_pg"]) / reg["sa_pg"] * 100)
    ga_delta      = reg["ga_pg"] - play["ga_pg"]   # positive = improvement

    ctx = {
        "ott_logo":      _logo_uri("OTT"),
        "goalie_photo":  _file_to_data_uri(PLAYERS_DIR / "gwyneth_philips.jpg"),
        "goalie_name":   "Gwyneth Phillips",
        "goalie_last":   "Phillips",

        "sf_reg":        f"{reg['sf_pg']:.1f}",
        "sf_play":       f"{play['sf_pg']:.1f}",
        "sf_delta":      f"{abs(play['sf_pg'] - reg['sf_pg']):.1f}",

        "gf_reg":        f"{reg['gf_pg']:.2f}",
        "gf_play":       f"{play['gf_pg']:.2f}",
        "gf_delta":      f"{play['gf_pg'] - reg['gf_pg']:.2f}",

        "sa_reg":        f"{reg['sa_pg']:.1f}",
        "sa_play":       f"{play['sa_pg']:.1f}",
        "sa_delta":      f"{play['sa_pg'] - reg['sa_pg']:.1f}",
        "sa_pct_change": sa_pct_change,

        "ga_reg":        f"{reg['ga_pg']:.2f}",
        "ga_play_pg":    f"{play['ga_pg']:.2f}",
        "ga_delta":      f"{ga_delta:.2f}",
        "ga_cell_class": "pos-hi",
        "ga_val_class":  "pos",
        "ga_badge_class": "up-good",
        "ga_arrow":      "&#9660;",

        "sv_reg":        f".{round(reg['sv_pct'] * 1000):03d}",
        "sv_play":       f".{round(play['sv_pct'] * 1000):03d}",
        "sv_delta":      f".{round((play['sv_pct'] - reg['sv_pct']) * 1000):03d}",
        "sv_cell_class": "pos-hi",
        "sv_val_class":  "pos",
        "sv_badge_class": "up-good",
        "sv_arrow":      "&#9650;",

        "gf_cell_class": "pos-hi",
        "gf_val_class":  "pos",
        "gf_badge_class": "up-good",
        "gf_arrow":      "&#9650;",

        "playoff_opp_label": "4 Games vs BOS",

        "insight_head": "The Phillips Effect",
        "insight_text": (
            f"OTT allowed <strong>+{sa_pct_change}% more shots</strong> per game in the playoffs — "
            f"but Phillips elevated her game to a <strong>.{round(play['sv_pct']*1000):03d} SV%</strong>, "
            f"holding Boston to just <strong>{play['ga_tot']} goals</strong> across 4 games."
        ),
    }

    print(f"\n  Rendering slide...")
    _render(ctx, "ott_transformation", out_dir)
    print(f"  Done — {out_dir / 'ott_transformation.png'}")


if __name__ == "__main__":
    run()
