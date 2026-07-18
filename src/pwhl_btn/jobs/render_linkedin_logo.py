"""
render_linkedin_logo.py — Render the BTN LinkedIn brand card to PNG.

Screenshots linkedin_logo.html at 1080×1080 and writes to output/.

Usage:
    python -m pwhl_btn.jobs.render_linkedin_logo
    python -m pwhl_btn.jobs.render_linkedin_logo --out path/to/output.png
"""

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

TEMPLATE_FILE = Path(__file__).resolve().parents[1] / "render" / "templates" / "linkedin_logo.html"
OUTPUT_DIR    = Path(__file__).resolve().parents[4] / "output"


def render(out_path: Path | None = None) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    dest = out_path or OUTPUT_DIR / "linkedin_logo.png"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 540, "height": 540})
        page.goto(f"file://{TEMPLATE_FILE.resolve()}")
        page.wait_for_timeout(800)
        page.screenshot(path=str(dest), clip={"x": 0, "y": 0, "width": 540, "height": 540})
        browser.close()

    print(f"  Saved → {dest}")
    return dest


def main():
    parser = argparse.ArgumentParser(description="Render BTN LinkedIn logo to PNG")
    parser.add_argument("--out", type=Path, default=None,
                        help="Output path (default: output/linkedin_logo.png)")
    args = parser.parse_args()

    print("\n── BTN LinkedIn Logo Render ────────────────────────────────────")
    render(args.out)
    print("─" * 60)


if __name__ == "__main__":
    main()
