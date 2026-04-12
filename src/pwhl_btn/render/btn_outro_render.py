"""
btn_outro_render.py — Render the BTN outro/closing slide.

Usage:
    python -m pwhl_btn.render.btn_outro_render
"""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

TEMPLATE_DIR = Path(__file__).parent / "templates"
OUTPUT_DIR   = Path(__file__).parent / "output"


def render_btn_outro(out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    env  = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    html = env.get_template("btn_outro.html").render()

    html_path = out_dir / "_render_btn_outro.html"
    html_path.write_text(html, encoding="utf-8")

    out_path = out_dir / "btn_outro.png"
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page    = browser.new_page(viewport={"width": 1080, "height": 1920})
        page.goto(f"file://{html_path.resolve()}")
        page.wait_for_timeout(900)
        page.screenshot(path=str(out_path), full_page=False)
        browser.close()

    html_path.unlink(missing_ok=True)
    print(f"✅ {out_path}")
    return out_path


if __name__ == "__main__":
    render_btn_outro()
