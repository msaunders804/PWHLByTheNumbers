"""
run_final_champion.py — Walter Cup Champion closing slide (MTL).
Usage: python -m pwhl_btn.jobs.run_final_champion
"""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

from pwhl_btn.db.db_queries import _logo_uri

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "render" / "templates"
OUTPUT_DIR   = Path(__file__).resolve().parents[3] / "src" / "pwhl_btn" / "render" / "output"


def _render(data: dict, slug: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    env  = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    html = env.get_template("final_champion.html").render(**data)

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

    ctx = {
        "logo":    _logo_uri("MTL"),
        "eyebrow": "BTN Model Prediction",
        "win_pct": 73,
    }

    print("\n=== Walter Cup Champion Slide ===")
    _render(ctx, "final_champion", out_dir)
    print(f"Done — {out_dir / 'final_champion.png'}")


if __name__ == "__main__":
    run()
