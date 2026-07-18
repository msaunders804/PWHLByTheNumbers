"""
run_final_h2h_hook.py — Walter Cup Final head-to-head hook slide.
  Split-screen: Marie-Philip Poulin (MTL) vs Brianne Jenner (OTT).
Usage: python -m pwhl_btn.jobs.run_final_h2h_hook
"""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

from pwhl_btn.db.db_queries import _logo_uri, _file_to_data_uri, PLAYERS_DIR

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "render" / "templates"
OUTPUT_DIR   = Path(__file__).resolve().parents[3] / "src" / "pwhl_btn" / "render" / "output"

# Official player photos are stored as assets/players/official/<player_id>.jpg
def _official_photo(player_id: int) -> str | None:
    p = PLAYERS_DIR / "official" / f"{player_id}.jpg"
    return _file_to_data_uri(p)


def _render(data: dict, slug: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    env  = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    html = env.get_template("final_h2h_hook.html").render(**data)

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

    photos_dir   = PLAYERS_DIR
    photo_jenner = _file_to_data_uri(photos_dir / "brianne_jenner.jpg")
    photo_poulin = _file_to_data_uri(photos_dir / "marie_philip_poulin.webp")

    ctx = {
        # Left side: MTL / Poulin
        "team_a":       "MTL",
        "name_a":       "Montréal Victoire",
        "logo_a":       _logo_uri("MTL"),
        "photo_a":      photo_poulin,
        "player_a_name": "Marie-Philip\nPoulin",
        "player_a_pos": "Forward · Montréal",

        # Right side: OTT / Jenner
        "team_b":       "OTT",
        "name_b":       "Ottawa Charge",
        "logo_b":       _logo_uri("OTT"),
        "photo_b":      photo_jenner,
        "player_b_name": "Brianne\nJenner",
        "player_b_pos": "Forward · Ottawa",
    }

    print("\n=== Walter Cup Final H2H Hook ===")
    _render(ctx, "final_h2h_hook", out_dir)
    print(f"Done — {out_dir / 'final_h2h_hook.png'}")


if __name__ == "__main__":
    run()
