"""
clinch_render.py — Renders the playoff clinch announcement slide.

Produces a single 1080×1920 PNG showing:
  - Team name + logo
  - "PLAYOFF BOUND" headline with seed
  - Top scorer (season stats)
  - Top goalie (season stats)
  - BTN branding

Usage:
    from pwhl_btn.render.clinch_render import render_clinch_slide
    render_clinch_slide(data, out_dir=Path("render/output"))
"""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

TEMPLATE_DIR = Path(__file__).parent / "templates"
OUTPUT_DIR   = Path(__file__).parent / "output"

ORDINAL = {1: "1ST", 2: "2ND", 3: "3RD", 4: "4TH"}


def render_clinch_slide(data: dict, out_dir: Path | None = None) -> Path:
    """
    Render the clinch announcement slide to a PNG.

    Args:
        data:    dict returned by db_queries.get_clinch_slide_data()
        out_dir: output directory (defaults to render/output/)

    Returns:
        Path to the output PNG.
    """
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    # Enrich data with derived display values
    data = dict(data)
    data.setdefault("seed_label", ORDINAL.get(data.get("seed"), f"{data.get('seed')}TH"))

    env  = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    tmpl = env.get_template("clinch_slide.html")
    html = tmpl.render(**data)

    code      = data.get("team_code", "TEAM").upper()
    html_path = out_dir / f"_render_clinch_{code}.html"
    html_path.write_text(html, encoding="utf-8")

    out_path = out_dir / f"clinch_{code}.png"
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page    = browser.new_page(viewport={"width": 1080, "height": 1920})
        page.goto(f"file://{html_path.resolve()}")
        page.wait_for_timeout(900)
        page.screenshot(path=str(out_path), full_page=False)
        browser.close()

    html_path.unlink(missing_ok=True)
    print(f"  ✅ {out_path.name}")
    return out_path


def render_clinch_announcement(data: dict, out_dir: Path | None = None) -> Path:
    """
    Render the simple clinch announcement graphic (logo + CLINCHED) to a PNG.

    Args:
        data:    dict with at least team_code, team_name, team_logo, seed_label.
                 Compatible with the dict returned by get_clinch_slide_data().
        out_dir: output directory (defaults to render/output/)

    Returns:
        Path to the output PNG.
    """
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    data = dict(data)
    data.setdefault("seed_label", ORDINAL.get(data.get("seed"), f"{data.get('seed')}TH"))

    env  = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    tmpl = env.get_template("clinch_announcement.html")
    html = tmpl.render(**data)

    code      = data.get("team_code", "TEAM").upper()
    html_path = out_dir / f"_render_clinch_announce_{code}.html"
    html_path.write_text(html, encoding="utf-8")

    out_path = out_dir / f"clinch_announcement_{code}.png"
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page    = browser.new_page(viewport={"width": 1080, "height": 1920})
        page.goto(f"file://{html_path.resolve()}")
        page.wait_for_timeout(900)
        page.screenshot(path=str(out_path), full_page=False)
        browser.close()

    html_path.unlink(missing_ok=True)
    print(f"  ✅ {out_path.name}")
    return out_path
