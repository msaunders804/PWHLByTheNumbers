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


def _generate_blurb(data: dict, retries: int = 3, retry_delay: int = 12) -> str:
    """Ask Claude to write a 3-4 sentence analysis blurb for the carousel."""
    import os
    import time
    import anthropic

    scorers_text = ", ".join(
        f"{s['name']} ({s['goals']}G {s['assists']}A {s['points']} pts)"
        for s in data.get("scorers", [])
    )
    games_text = ", ".join(
        f"a {g['our_score']}–{g['opp_score']} win over {g['opponent']} on {g['date']} (+{g['diff']})"
        for g in data.get("top_games", [])
    )
    g = data.get("goalie", {})

    prompt = (
        f"Write a 3-4 sentence Instagram carousel blurb (no hashtags, no emojis, no markdown) "
        f"about why the {data['team_name']} are in the 2025-26 PWHL playoffs. "
        f"Key facts to weave in: "
        f"Record {data['record_str']} ({data['points']} points, {data['win_pct']} win%), "
        f"top scorers: {scorers_text}, "
        f"goalie {g.get('name','—')} with {g.get('shutouts',0)} shutouts, "
        f"{g.get('gaa','—')} GAA, {g.get('sv_pct','—')} SV%, "
        f"and their most dominant wins this season: {games_text}. "
        f"Reference at least one specific game by date and score. "
        f"Keep it punchy, factual, and fan-friendly. Do not use bullet points."
    )

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()
        except Exception as exc:
            last_exc = exc
            if attempt < retries:
                print(f"  [blurb] Attempt {attempt} failed ({exc.__class__.__name__}) — retrying in {retry_delay}s…")
                time.sleep(retry_delay)
    raise last_exc


def render_clinch_carousel(data: dict, out_dir: Path | None = None) -> list[Path]:
    """
    Render the full clinch carousel (6 slides) for a team.

    Slides:
      0 — Cover        (team logo + Road to the Playoffs)
      1 — Top Scorers  (3 players with photos)
      2 — Top Games    (3 highest goal-differential wins)
      3 — Season Record (win %, W-L-OTL grid)
      4 — Goalie       (shutouts, GAA, SV% with photo bg)
      5 — Blurb        (Claude-generated analysis)

    Args:
        data:    dict returned by db_queries.get_clinch_carousel_data()
        out_dir: output directory (defaults to render/output/)

    Returns:
        List of Paths to generated PNGs, in slide order.
    """
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    data = dict(data)

    print("  Generating analysis blurb via Claude…")
    try:
        data["blurb"] = _generate_blurb(data)
    except Exception as exc:
        print(f"  [blurb] Claude API error: {exc} — using placeholder")
        data["blurb"] = (
            f"The {data['team_name']} earned their playoff spot through relentless "
            f"consistency and elite play on both ends of the ice all season long."
        )

    slides = [
        ("carousel_cover.html",   "cover"),
        ("carousel_scorers.html", "scorers"),
        ("carousel_games.html",   "games"),
        ("carousel_record.html",  "record"),
        ("carousel_goalie.html",  "goalie"),
        ("carousel_blurb.html",   "blurb"),
    ]

    env    = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    code   = data.get("team_code", "TEAM").upper()
    outputs: list[Path] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for tmpl_name, label in slides:
            tmpl      = env.get_template(tmpl_name)
            html      = tmpl.render(**data)
            html_path = out_dir / f"_render_carousel_{code}_{label}.html"
            html_path.write_text(html, encoding="utf-8")

            out_path = out_dir / f"carousel_{code}_{label}.png"
            page     = browser.new_page(viewport={"width": 1080, "height": 1920})
            page.goto(f"file://{html_path.resolve()}")
            page.wait_for_timeout(900)
            page.screenshot(path=str(out_path), full_page=False)
            page.close()
            html_path.unlink(missing_ok=True)
            print(f"  ✅ {out_path.name}")
            outputs.append(out_path)
        browser.close()

    return outputs


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
