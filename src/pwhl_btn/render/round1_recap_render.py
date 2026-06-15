"""
round1_recap_render.py — Round 1 playoff recap slides (2 per series).
  Slide 1: Hook — player photo + "ROUND 1 RECAP" + series result
  Slide 2: Bullets — 5–6 key stats with large callout numbers
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


def render_hook(data: dict, slug: str = "recap_hook", out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    html = _make_env().get_template("recap_hook.html").render(**data)
    return _screenshot(html, slug, out_dir)


def render_bullets(data: dict, slug: str = "recap_bullets", out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    html = _make_env().get_template("recap_bullets.html").render(**data)
    return _screenshot(html, slug, out_dir)


def render_results_cover(data: dict, slug: str = "recap_00_results_cover", out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    html = _make_env().get_template("recap_results_cover.html").render(**data)
    return _screenshot(html, slug, out_dir)
