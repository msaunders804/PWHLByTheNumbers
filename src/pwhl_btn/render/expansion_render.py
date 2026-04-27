"""
expansion_render.py — Renders expansion city slides as 1080x1920 PNGs.
"""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

TEMPLATE_DIR = Path(__file__).parent / "templates"
OUTPUT_DIR   = Path(__file__).parent / "output"
ASSETS_DIR   = Path(__file__).resolve().parents[3] / "assets" / "cities"

# ── Per-city structured data ──────────────────────────────────────────────────
# Keyed by city name (matches expansion_cities.json candidates[].city)

CITY_EXTRA: dict[str, dict] = {
    "Washington": {
        "image_file":   "washington.jpg",
        "nhl_arena":    "Capital One Arena",
        "nhl_capacity": "20,356",
        "womens_teams": [
            ("Washington Spirit",  "NWSL"),
            ("Washington Mystics", "WNBA"),
        ],
        "womens_none_text": "",
    },
    "Calgary": {
        "image_file":   "calgary.jpg",
        "nhl_arena":    "Scotiabank Saddledome",
        "nhl_capacity": "19,289",
        "womens_teams": [],
        "womens_none_text": "No top-tier women's pro league — strong amateur hockey roots across Alberta",
    },
    "Denver": {
        "image_file":   "denver.jpg",
        "nhl_arena":    "Ball Arena",
        "nhl_capacity": "18,187",
        "womens_teams": [
            ("Colorado Spirit", "NWSL — Expansion 2026"),
        ],
        "womens_none_text": "",
    },
    "Detroit": {
        "image_file":   "detroit.jpg",
        "nhl_arena":    "Little Caesars Arena",
        "nhl_capacity": "19,515",
        "womens_teams": [],
        "womens_none_text": "No NWSL or WNBA franchise — proven hockey appetite, untapped women's sports market",
    },
    "Chicago": {
        "image_file":   "chicago.jpg",
        "nhl_arena":    "United Center",
        "nhl_capacity": "19,717",
        "womens_teams": [
            ("Chicago Red Stars", "NWSL"),
            ("Chicago Sky",       "WNBA"),
        ],
        "womens_none_text": "",
    },
    "St. Louis": {
        "image_file":   "st Louis.jpg",
        "nhl_arena":    "Enterprise Center",
        "nhl_capacity": "18,096",
        "womens_teams": [],
        "womens_none_text": "No NWSL or WNBA franchise — strongest untapped hockey market in the data",
    },
    "Raleigh": {
        "image_file":   None,
        "nhl_arena":    "Lenovo Center",
        "nhl_capacity": "18,680",
        "womens_teams": [
            ("NC Courage", "NWSL"),
        ],
        "womens_none_text": "",
    },
    "Buffalo": {
        "image_file":   None,
        "nhl_arena":    "KeyBank Center",
        "nhl_capacity": "19,070",
        "womens_teams": [],
        "womens_none_text": "No NWSL or WNBA franchise",
    },
    "Edmonton": {
        "image_file":   None,
        "nhl_arena":    "Rogers Place",
        "nhl_capacity": "18,347",
        "womens_teams": [],
        "womens_none_text": "No NWSL or WNBA franchise — strong amateur hockey roots across Alberta",
    },
    "Halifax": {
        "image_file":   None,
        "nhl_arena":    "Scotiabank Centre",
        "nhl_capacity": "10,595",
        "womens_teams": [],
        "womens_none_text": "No professional women's sports franchise in market",
    },
}


def _make_env() -> Environment:
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
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
        page.wait_for_timeout(1500)
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
    data: one entry from score_cities(), with 'total' added by the job runner.
    """
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    city    = data["city"]
    extra   = CITY_EXTRA.get(city, {})

    # Resolve city image path
    image_file = extra.get("image_file")
    if image_file and (ASSETS_DIR / image_file).exists():
        city_image_path = (ASSETS_DIR / image_file).resolve().as_posix()
    else:
        city_image_path = ""

    # Format attendance with commas
    avg_att = data["tour_avg_att"]
    tour_avg_fmt = f"{avg_att:,}" if avg_att else ""

    ctx = {
        "rank":             data["rank"],
        "total":            data["total"],
        "city":             data["city"],
        "state_province":   data["state_province"],
        "country":          data["country"],
        "nhl_team":         data["nhl_team"],
        "nhl_arena":        extra.get("nhl_arena", ""),
        "nhl_capacity":     extra.get("nhl_capacity", ""),
        "womens_teams":     extra.get("womens_teams", []),
        "womens_none_text": extra.get("womens_none_text", "No professional women's sports franchise in market"),
        "tour_avg_att":     tour_avg_fmt,
        "tour_game_count":  data["tour_game_count"],
        "composite":        f"{data['composite_score']:.2f}",
        "narrative_hook":   data["narrative_hook"],
        "city_image_path":  city_image_path,
    }

    slug = f"expansion_{data['rank']:02d}_{city.lower().replace(' ', '_').replace('.', '')}"
    html = _make_env().get_template("expansion_city.html").render(**ctx)
    return _screenshot(html, slug, out_dir)


def render_expansion_methodology(out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    html = _make_env().get_template("expansion_methodology.html").render()
    return _screenshot(html, "expansion_99_methodology", out_dir)


def render_expansion_rankings(all_cities: list[dict], out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    cities = [
        {
            "rank":           c["rank"],
            "city":           c["city"],
            "state_province": c["state_province"],
            "country":        c["country"],
            "composite":      f"{c['composite_score']:.2f}",
        }
        for c in sorted(all_cities, key=lambda x: x["rank"])
    ]
    html = _make_env().get_template("expansion_rankings.html").render(cities=cities)
    return _screenshot(html, "expansion_96_rankings", out_dir)


def render_expansion_surprises(out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    html = _make_env().get_template("expansion_surprises.html").render()
    return _screenshot(html, "expansion_97_surprises", out_dir)


def render_expansion_honorable_mention(all_cities: list[dict], out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    hm_names = {"St. Louis", "Raleigh", "Chicago"}
    cities = []
    for data in all_cities:
        if data["city"] not in hm_names:
            continue
        extra = CITY_EXTRA.get(data["city"], {})
        avg_att = data["tour_avg_att"]
        cities.append({
            "city":             data["city"],
            "state_province":   data["state_province"],
            "country":          data["country"],
            "nhl_team":         data["nhl_team"],
            "nhl_arena":        extra.get("nhl_arena", ""),
            "womens_teams":     extra.get("womens_teams", []),
            "womens_none_text": extra.get("womens_none_text", "None"),
            "tour_avg_att":     f"{avg_att:,}" if avg_att else "",
            "composite":        f"{data['composite_score']:.2f}",
            "narrative_hook":   data["narrative_hook"],
        })
    # sort: STL, Raleigh, Buffalo
    cities.sort(key=lambda c: -float(c["composite"]))
    html = _make_env().get_template("expansion_honorable_mention.html").render(cities=cities)
    return _screenshot(html, "expansion_98_honorable_mention", out_dir)
