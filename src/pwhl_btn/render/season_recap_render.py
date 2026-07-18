"""
season_recap_render.py — Renders 4-slide season recap carousel per team.
  Slide 1: Hook — team logo + "2025-26 Season Recap" + record
  Slide 2: Offense — shots, goals, goal leader, points leader
  Slide 3: Defence — shots against, shutouts, SV%, top goalie
  Slide 4: Fun — home/away wins, OT wins, PIM, plus/minus leader
"""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

TEMPLATE_DIR = Path(__file__).parent / "templates"
OUTPUT_DIR   = Path(__file__).parent / "output"


def _make_env() -> Environment:
    return Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))


def _screenshot(html: str, slug: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
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


def render_hook(data: dict, team_code: str, out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    html = _make_env().get_template("season_recap_hook.html").render(**data)
    return _screenshot(html, f"season_recap_{team_code.lower()}_01_hook", out_dir)


def render_offense(data: dict, team_code: str, out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    html = _make_env().get_template("season_recap_offense.html").render(**data)
    return _screenshot(html, f"season_recap_{team_code.lower()}_02_offense", out_dir)


def render_defense(data: dict, team_code: str, out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    html = _make_env().get_template("season_recap_defense.html").render(**data)
    return _screenshot(html, f"season_recap_{team_code.lower()}_03_defense", out_dir)


def render_fun(data: dict, team_code: str, out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    html = _make_env().get_template("season_recap_fun.html").render(**data)
    return _screenshot(html, f"season_recap_{team_code.lower()}_04_fun", out_dir)


def render_all_slides(data: dict, out_dir: Path | None = None) -> list[Path]:
    """Render all 4 slides for one team. Returns list of output paths."""
    code = data["team_code"]
    return [
        render_hook(data, code, out_dir),
        render_offense(data, code, out_dir),
        render_defense(data, code, out_dir),
        render_fun(data, code, out_dir),
    ]
