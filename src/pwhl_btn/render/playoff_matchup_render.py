"""
playoff_matchup_render.py — Renders playoff matchup carousel slides.
Generic 5-slide set: cover, season series, game log, scorers, goaltending.
Plus historical context slide.
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


def render_cover(data: dict, out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    html = _make_env().get_template("playoff_matchup_cover.html").render(**data)
    return _screenshot(html, "playoff_h2h_01_cover", out_dir)


def render_cover_ott(data: dict, out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    html = _make_env().get_template("playoff_matchup_cover_ott.html").render(**data)
    return _screenshot(html, "playoff_ob_01_cover", out_dir)


def render_series(data: dict, slug: str = "playoff_h2h_02_series", out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    html = _make_env().get_template("playoff_h2h_series.html").render(**data)
    return _screenshot(html, slug, out_dir)


def render_games(data: dict, slug: str = "playoff_h2h_03_games", out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    html = _make_env().get_template("playoff_h2h_games.html").render(**data)
    return _screenshot(html, slug, out_dir)


def render_scorers(data: dict, slug: str = "playoff_h2h_04_scorers", out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    html = _make_env().get_template("playoff_h2h_scorers.html").render(**data)
    return _screenshot(html, slug, out_dir)


def render_goalie(data: dict, slug: str = "playoff_h2h_05_goalie", out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    html = _make_env().get_template("playoff_h2h_goalie.html").render(**data)
    return _screenshot(html, slug, out_dir)


def render_mm_stats(data: dict, out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    html = _make_env().get_template("playoff_mm_stats.html").render(**data)
    return _screenshot(html, "playoff_h2h_04_stats", out_dir)


def render_historical(data: dict, out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    html = _make_env().get_template("playoff_historical.html").render(**data)
    return _screenshot(html, "playoff_historical", out_dir)
