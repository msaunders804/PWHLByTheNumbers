"""
eliminated_render.py — Renders playoff elimination and Gold Plan slides.

Produces 1080×1920 PNGs:
  1. eliminated_announcement_{TEAM}.png  — ELIMINATED card
  2. gold_plan_standings.png             — Gold Plan standings table
  3. gold_plan_rules.png                 — Gold Plan rules + PWHL vs. other leagues

Usage:
    from pwhl_btn.render.eliminated_render import (
        render_eliminated_announcement,
        render_gold_plan_standings,
        render_gold_plan_rules,
    )
"""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

TEMPLATE_DIR = Path(__file__).parent / "templates"
OUTPUT_DIR   = Path(__file__).parent / "output"


def render_eliminated_announcement(data: dict, out_dir: Path | None = None) -> Path:
    """
    Render the elimination announcement graphic (logo + ELIMINATED + Gold Plan badge).

    Args:
        data:    dict with keys:
                   team_code        str   e.g. "SEA"
                   team_name        str   e.g. "Seattle Torrent"
                   team_logo        str   data URI or None
                   elimination_date str   e.g. "April 14, 2026"
        out_dir: output directory (defaults to render/output/)

    Returns:
        Path to the output PNG.
    """
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    env  = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    tmpl = env.get_template("eliminated_announcement.html")
    html = tmpl.render(**data)

    code      = data.get("team_code", "TEAM").upper()
    html_path = out_dir / f"_render_eliminated_{code}.html"
    html_path.write_text(html, encoding="utf-8")

    out_path = out_dir / f"eliminated_{code}.png"
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page    = browser.new_page(viewport={"width": 1080, "height": 1920})
        page.goto(f"file://{html_path.resolve()}")
        page.wait_for_timeout(900)
        page.screenshot(path=str(out_path), full_page=False)
        browser.close()

    html_path.unlink(missing_ok=True)
    print(f"  [ok] {out_path.name}")
    return out_path


def render_gold_plan_standings(data: dict, out_dir: Path | None = None) -> Path:
    """
    Render the Gold Plan standings slide (slide 2).

    Args:
        data:    dict with keys:
                   updated_through  str        e.g. "April 15, 2026"
                   standings        list[dict] each row:
                       team_code       str | None
                       team_name       str | None
                       team_logo       str | None  (data URI)
                       gold_pts        int | None
                       elim_date       str | None  e.g. "Apr 14"
                       games_remaining int | None
        out_dir: output directory (defaults to render/output/)

    Returns:
        Path to the output PNG.
    """
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    env  = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    tmpl = env.get_template("gold_plan_standings.html")
    html = tmpl.render(**data)

    html_path = out_dir / "_render_gold_plan_standings.html"
    html_path.write_text(html, encoding="utf-8")

    out_path = out_dir / "gold_plan_standings.png"
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page    = browser.new_page(viewport={"width": 1080, "height": 1920})
        page.goto(f"file://{html_path.resolve()}")
        page.wait_for_timeout(900)
        page.screenshot(path=str(out_path), full_page=False)
        browser.close()

    html_path.unlink(missing_ok=True)
    print(f"  [ok] {out_path.name}")
    return out_path


def render_gold_plan_rules(out_dir: Path | None = None) -> Path:
    """
    Render the Gold Plan rules explainer slide (slide 3).

    No dynamic data needed — all content is baked into the template.

    Args:
        out_dir: output directory (defaults to render/output/)

    Returns:
        Path to the output PNG.
    """
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    env  = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    tmpl = env.get_template("gold_plan_rules.html")
    html = tmpl.render()

    html_path = out_dir / "_render_gold_plan_rules.html"
    html_path.write_text(html, encoding="utf-8")

    out_path = out_dir / "gold_plan_rules.png"
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page    = browser.new_page(viewport={"width": 1080, "height": 1920})
        page.goto(f"file://{html_path.resolve()}")
        page.wait_for_timeout(900)
        page.screenshot(path=str(out_path), full_page=False)
        browser.close()

    html_path.unlink(missing_ok=True)
    print(f"  [ok] {out_path.name}")
    return out_path
