"""
expansion_render.py — Renders expansion city slides as 1080x1920 PNGs.
"""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, pass_environment
from playwright.sync_api import sync_playwright

TEMPLATE_DIR = Path(__file__).parent / "templates"
OUTPUT_DIR   = Path(__file__).parent / "output"


def _make_env() -> Environment:
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    env.filters["format_number"] = lambda v: f"{int(v):,}"
    return env


def _screenshot(html: str, slug: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / f"_render_{slug}.html"
    html_path.write_text(html, encoding="utf-8")
    out_path = out_dir / f"{slug}.png"
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1920})
        page.goto(f"file://{html_path.resolve()}")
        page.wait_for_timeout(1200)
        page.screenshot(path=str(out_path), full_page=False)
        browser.close()
    html_path.unlink(missing_ok=True)
    print(f"  [ok] {out_path.name}")
    return out_path


def render_expansion_cover(city_count: int, out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    env  = _make_env()
    html = env.get_template("expansion_cover.html").render(city_count=city_count)
    return _screenshot(html, "expansion_00_cover", out_dir)


def render_expansion_city(data: dict, out_dir: Path | None = None) -> Path:
    """
    data keys:
      rank, total, city, state_province, country, nhl_team,
      tour_avg_att, tour_game_count,
      pillar_scores  { nhl_market, tour_attendance, womens_sports, arena_fit, geo_balance }
      composite_score, narrative_hook,
      womens_sports_notes  (short label shown under women's bar)
    """
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    ps = data["pillar_scores"]

    def pct(score: float) -> int:
        return round((score / 10) * 100)

    # Short women's teams label extracted from notes (first sentence)
    notes = data.get("womens_sports_notes", "")
    womens_teams = notes.split(".")[0] if notes else ""
    if len(womens_teams) > 70:
        womens_teams = womens_teams[:67] + "..."

    ctx = {
        "rank":          data["rank"],
        "total":         data["total"],
        "city":          data["city"],
        "state_province": data["state_province"],
        "country":       data["country"],
        "nhl_team":      data["nhl_team"],
        "tour_avg_att":  data["tour_avg_att"],
        "tour_game_count": data["tour_game_count"],
        "tour_score":    f"{ps['tour_attendance']:.1f}",
        "tour_pct":      pct(ps["tour_attendance"]),
        "nhl_score":     f"{ps['nhl_market']:.1f}",
        "nhl_pct":       pct(ps["nhl_market"]),
        "womens_score":  f"{ps['womens_sports']:.1f}",
        "womens_pct":    pct(ps["womens_sports"]),
        "womens_teams":  womens_teams,
        "composite":     f"{data['composite_score']:.2f}",
        "narrative_hook": data["narrative_hook"],
    }

    slug = f"expansion_{data['rank']:02d}_{data['city'].lower().replace(' ', '_')}"
    env  = _make_env()
    html = env.get_template("expansion_city.html").render(**ctx)
    return _screenshot(html, slug, out_dir)
