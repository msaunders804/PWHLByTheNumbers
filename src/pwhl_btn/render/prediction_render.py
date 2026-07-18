"""
prediction_render.py — Renders playoff prediction carousel slides.
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


def render_pred_cover(data: dict, out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    html = _make_env().get_template("pred_cover.html").render(**data)
    return _screenshot(html, "pred_01_cover", out_dir)


def render_pred_matchup(data: dict, slug_suffix: str, out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    html = _make_env().get_template("pred_matchup.html").render(**data)
    return _screenshot(html, f"pred_{slug_suffix}", out_dir)


def render_pred_bayes_shift(data: dict, out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    html = _make_env().get_template("pred_bayes_shift.html").render(**data)
    return _screenshot(html, "pred_04_bayes_shift", out_dir)


def render_pred_methodology(data: dict, out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    html = _make_env().get_template("pred_methodology.html").render(**data)
    return _screenshot(html, "pred_05_methodology", out_dir)


def render_pred_hook_ott(data: dict, out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    html = _make_env().get_template("pred_hook_ott.html").render(**data)
    return _screenshot(html, "pred_hook_ott", out_dir)
