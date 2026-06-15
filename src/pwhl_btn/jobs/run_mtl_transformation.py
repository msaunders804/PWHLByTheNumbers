"""
run_mtl_transformation.py — Montréal Victoire regular season vs playoff stat comparison.
Usage: python -m pwhl_btn.jobs.run_mtl_transformation
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

MTL_TEAM_ID = 3

engine = get_engine(pool_pre_ping=True)


def _load_stats(season_id: int) -> dict:
    with Session(engine) as s:
        goalie = s.execute(text("""
            SELECT COUNT(DISTINCT games.game_id) gp,
                   SUM(ggs.shots_against)        sa,
                   SUM(ggs.saves)                saves
            FROM games
            JOIN goalie_game_stats ggs
              ON ggs.game_id = games.game_id AND ggs.team_id = :tid
            WHERE games.season_id = :sid AND games.game_status = 'final'
        """), {"tid": MTL_TEAM_ID, "sid": season_id}).fetchone()

        skater = s.execute(text("""
            SELECT SUM(pgs.shots) sf
            FROM games
            JOIN player_game_stats pgs
              ON pgs.game_id = games.game_id AND pgs.team_id = :tid
            WHERE games.season_id = :sid AND games.game_status = 'final'
        """), {"tid": MTL_TEAM_ID, "sid": season_id}).fetchone()

        scores = s.execute(text("""
            SELECT COUNT(*) gp,
                   SUM(CASE WHEN g.home_team_id=:tid THEN g.home_score ELSE g.away_score END) gf,
                   SUM(CASE WHEN g.home_team_id=:tid THEN g.away_score ELSE g.home_score END) ga
            FROM games g
            WHERE g.season_id=:sid AND g.game_status='final'
              AND (g.home_team_id=:tid OR g.away_team_id=:tid)
        """), {"tid": MTL_TEAM_ID, "sid": season_id}).fetchone()

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

    print("\n=== Montreal Victoire: Regular Season vs Playoffs ===")

    reg  = _load_stats(season_id=8)
    play = _load_stats(season_id=9)

    print(f"  Regular season ({reg['gp']} GP): SF/GP={reg['sf_pg']:.1f}  GF/GP={reg['gf_pg']:.2f}  SA/GP={reg['sa_pg']:.1f}  GA/GP={reg['ga_pg']:.2f}  SV%={reg['sv_pct']:.4f}")
    print(f"  Playoffs       ({play['gp']} GP): SF/GP={play['sf_pg']:.1f}  GF/GP={play['gf_pg']:.2f}  SA/GP={play['sa_pg']:.1f}  GA/GP={play['ga_pg']:.2f}  SV%={play['sv_pct']:.4f}")

    sa_pct_change = round((play["sa_pg"] - reg["sa_pg"]) / reg["sa_pg"] * 100)

    # GF/GP went DOWN for MTL — negative
    gf_up    = play["gf_pg"] > reg["gf_pg"]
    gf_delta = abs(play["gf_pg"] - reg["gf_pg"])

    # GA/GP went UP for MTL — negative (allowing more)
    ga_up    = play["ga_pg"] > reg["ga_pg"]
    ga_delta = abs(play["ga_pg"] - reg["ga_pg"])

    # SV% went DOWN for MTL — negative
    sv_up    = play["sv_pct"] > reg["sv_pct"]
    sv_delta = abs(play["sv_pct"] - reg["sv_pct"])

    ctx = {
        "ott_logo":      _logo_uri("MTL"),
        "goalie_photo":  _file_to_data_uri(PLAYERS_DIR / "ann_renee_desbiens.jpg"),
        "goalie_name":   "Ann-Renée Desbiens",
        "goalie_last":   "Desbiens",

        "sf_reg":        f"{reg['sf_pg']:.1f}",
        "sf_play":       f"{play['sf_pg']:.1f}",
        "sf_delta":      f"{abs(play['sf_pg'] - reg['sf_pg']):.1f}",

        "gf_reg":        f"{reg['gf_pg']:.2f}",
        "gf_play":       f"{play['gf_pg']:.2f}",
        "gf_delta":      f"{gf_delta:.2f}",
        "gf_cell_class": "pos-hi" if gf_up else "",
        "gf_val_class":  "pos" if gf_up else "",
        "gf_badge_class": "up-good" if gf_up else "down",
        "gf_arrow":      "&#9650;" if gf_up else "&#9660;",

        "sa_reg":        f"{reg['sa_pg']:.1f}",
        "sa_play":       f"{play['sa_pg']:.1f}",
        "sa_delta":      f"{play['sa_pg'] - reg['sa_pg']:.1f}",
        "sa_pct_change": sa_pct_change,

        "ga_reg":        f"{reg['ga_pg']:.2f}",
        "ga_play_pg":    f"{play['ga_pg']:.2f}",
        "ga_delta":      f"{ga_delta:.2f}",
        "ga_cell_class": "pos-hi" if not ga_up else "hi",
        "ga_val_class":  "pos" if not ga_up else "hi",
        "ga_badge_class": "up-good" if not ga_up else "up-warn",
        "ga_arrow":      "&#9660;" if not ga_up else "&#9650;",

        "sv_reg":        f".{round(reg['sv_pct'] * 1000):03d}",
        "sv_play":       f".{round(play['sv_pct'] * 1000):03d}",
        "sv_delta":      f".{round(sv_delta * 1000):03d}",
        "sv_cell_class": "pos-hi" if sv_up else "",
        "sv_val_class":  "pos" if sv_up else "",
        "sv_badge_class": "up-good" if sv_up else "down",
        "sv_arrow":      "&#9650;" if sv_up else "&#9660;",

        "playoff_opp_label": "5 Games vs MIN",

        "insight_head": "Playoff Reality Check",
        "insight_text": (
            f"Montréal dominated the regular season — a <strong>.{round(reg['sv_pct']*1000):03d} SV%</strong> "
            f"and just <strong>{reg['ga_pg']:.2f} GA/GP</strong>. "
            f"Minnesota pushed them to 5 games and forced <strong>+{sa_pct_change}% more shots</strong>, "
            f"a test that OTT will look to replicate in the Final."
        ),
    }

    print(f"\n  Rendering slide...")
    _render(ctx, "mtl_transformation", out_dir)
    print(f"  Done — {out_dir / 'mtl_transformation.png'}")


if __name__ == "__main__":
    run()
