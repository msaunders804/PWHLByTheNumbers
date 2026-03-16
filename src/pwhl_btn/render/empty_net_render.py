"""
empty_net_render.py — HTML/Playwright renderer for empty net analysis slides.

Takes the `results` dict produced by empty_net_analysis.analyze_games() and
renders four TikTok-format (1080x1920) PNG slides using Jinja2 templates and
Playwright.

Usage (called from empty_net_analysis.py):
    from pwhl_btn.render.empty_net_render import render_all
    render_all(results, out_dir=Path("visualizations/output"))
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

TEMPLATE_DIR = Path(__file__).parent / "templates"
OUTPUT_DIR   = Path(__file__).parent / "output"

TEAM_COLORS = {
    "BOS": "#007A33",   # Boston Fleet green
    "MIN": "#813EA0",   # Minnesota Frost purple
    "MTL": "#862633",   # Montreal Victoire red
    "NY":  "#00b2a9",   # New York Sirens teal
    "OTT": "#c8102e",   # Ottawa Charge red
    "TOR": "#00205b",   # Toronto Sceptres navy
    "SEA": "#005c5c",   # Seattle
    "VAN": "#00843d",   # Vancouver
}
_DEFAULT_COLOR = "#8c52ff"

_ASSETS_DIR = Path(__file__).resolve().parents[3] / "assets" / "logos"


# ── Logo helpers ───────────────────────────────────────────────────────────────

def _pwhl_logo_uri() -> str | None:
    for ext in ("png", "svg", "jpg", "webp"):
        p = _ASSETS_DIR / f"PWHL_logo.{ext}"
        if p.exists():
            return p.resolve().as_uri()
    return None


def _team_logo_uri(abbr: str) -> str | None:
    p = _ASSETS_DIR / f"{abbr}_50x50.png"
    if p.exists():
        return p.resolve().as_uri()
    return None


# ── Histogram SVG ─────────────────────────────────────────────────────────────

def _histogram_svg(pull_times: list[float], w: int = 900, h: int = 560) -> str:
    """Return a dark-themed SVG histogram of goalie pull timing."""
    if not pull_times:
        return "<svg></svg>"

    bins = np.arange(0, 1261, 60)          # 21 edges → 20 bins (0-19 min remaining)
    counts, _ = np.histogram(pull_times, bins=bins)
    max_count  = int(counts.max()) if counts.max() > 0 else 1
    avg        = float(np.mean(pull_times))

    pad_l, pad_r, pad_t, pad_b = 64, 24, 28, 64
    chart_w = w - pad_l - pad_r
    chart_h = h - pad_t - pad_b
    n_bins  = len(counts)
    bar_w   = chart_w / n_bins

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="{w}" height="{h}">'
    ]

    # Y grid lines + labels (4 steps)
    for step in range(1, 5):
        y     = pad_t + chart_h * (1 - step / 4)
        label = math.ceil(max_count * step / 4)
        parts.append(
            f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l + chart_w}" y2="{y:.1f}" '
            f'stroke="rgba(255,255,255,0.06)" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{pad_l - 8}" y="{y + 5:.1f}" fill="rgba(255,255,255,0.28)" '
            f'font-family="Barlow Condensed,sans-serif" font-size="18" text-anchor="end">'
            f'{label}</text>'
        )

    # Bars
    for i, cnt in enumerate(counts):
        if cnt == 0:
            continue
        bh  = (cnt / max_count) * chart_h
        bx  = pad_l + i * bar_w + 1.5
        by  = pad_t + chart_h - bh
        bww = bar_w - 3
        parts.append(
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bww:.1f}" height="{bh:.1f}" '
            f'fill="#8c52ff" rx="4" opacity="0.85"/>'
        )

    # Baseline
    parts.append(
        f'<line x1="{pad_l}" y1="{pad_t + chart_h}" '
        f'x2="{pad_l + chart_w}" y2="{pad_t + chart_h}" '
        f'stroke="rgba(255,255,255,0.15)" stroke-width="1.5"/>'
    )

    # Average line
    avg_x = pad_l + (avg / 1200) * chart_w
    parts.append(
        f'<line x1="{avg_x:.1f}" y1="{pad_t - 4}" '
        f'x2="{avg_x:.1f}" y2="{pad_t + chart_h}" '
        f'stroke="#f5a623" stroke-width="2.5" stroke-dasharray="10,5"/>'
    )

    # Average label
    avg_min = int(avg // 60)
    avg_sec = int(avg % 60)
    label_x = avg_x + 12
    anchor  = "start"
    if label_x + 130 > pad_l + chart_w:
        label_x = avg_x - 12
        anchor  = "end"
    parts.append(
        f'<text x="{label_x:.1f}" y="{pad_t + 22}" fill="#f5a623" '
        f'font-family="Barlow Condensed,sans-serif" font-size="21" font-weight="700" '
        f'text-anchor="{anchor}">AVG {avg_min}:{avg_sec:02d} LEFT</text>'
    )

    # X tick labels (every 2 minutes = 120 s)
    for s in range(0, 1201, 120):
        tx  = pad_l + (s / 1200) * chart_w
        mm  = s // 60
        ss  = s % 60
        parts.append(
            f'<text x="{tx:.1f}" y="{pad_t + chart_h + 26}" fill="rgba(255,255,255,0.38)" '
            f'font-family="Barlow Condensed,sans-serif" font-size="18" text-anchor="middle">'
            f'{mm}:{ss:02d}</text>'
        )

    # X axis label
    mx = pad_l + chart_w / 2
    parts.append(
        f'<text x="{mx:.1f}" y="{h - 2}" fill="rgba(255,255,255,0.2)" '
        f'font-family="Barlow Condensed,sans-serif" font-size="16" font-weight="700" '
        f'letter-spacing="2" text-anchor="middle">TIME REMAINING IN 3RD (MM:SS)</text>'
    )

    parts.append("</svg>")
    return "\n".join(parts)


# ── Slide data builders ────────────────────────────────────────────────────────

def _slide0_data(results: dict, pwhl_logo: str | None) -> dict:
    scored    = results.get("pull_scored",   0)
    no_score  = results.get("pull_no_score", 0)
    total     = scored + no_score or 1
    events = [
        {**ev, "logo": _team_logo_uri(ev["team"]), "opp_logo": _team_logo_uri(ev["opponent"])}
        for ev in results.get("pull_scored_events", [])
    ]
    return {
        "total_pulls":   total,
        "n_scored":      scored,
        "n_no_score":    no_score,
        "pct_scored":    round(scored   / total * 100),
        "pct_no_score":  round(no_score / total * 100),
        "events":        events,
        "pwhl_logo":     pwhl_logo,
    }


def _team_rows(data: dict, red_bars: bool = False) -> list[dict]:
    """Build sorted team row list for slides 1 and 2."""
    teams_sorted = sorted(data, key=lambda t: data[t], reverse=True)
    max_val = max(data.values()) if data else 1
    rows = []
    for abbr in teams_sorted:
        val = data[abbr]
        rows.append({
            "abbr":    abbr,
            "val":     val,
            "color":   TEAM_COLORS.get(abbr, _DEFAULT_COLOR) if not red_bars else "#ff4f4f",
            "bar_pct": round(val / max_val * 100),
        })
    return rows


def _slide1_data(results: dict, pwhl_logo: str | None) -> dict:
    # Count how many times each team scored after pulling the goalie
    pull_counts: dict[str, int] = {}
    for ev in results.get("pull_scored_events", []):
        pull_counts[ev["team"]] = pull_counts.get(ev["team"], 0) + 1
    return {
        "teams":     _team_rows(pull_counts),
        "pwhl_logo": pwhl_logo,
    }


def _slide2_data(results: dict, pwhl_logo: str | None) -> dict:
    return {
        "teams":     _team_rows(results["en_allowed"], red_bars=True),
        "pwhl_logo": pwhl_logo,
    }


def _slide3_data(results: dict, pwhl_logo: str | None) -> dict:
    pull_times = results["pull_times"]
    avg        = float(np.mean(pull_times)) if pull_times else 0.0
    return {
        "chart_svg": _histogram_svg(pull_times),
        "n_pulls":   len(pull_times),
        "avg_min":   int(avg // 60),
        "avg_sec":   int(avg % 60),
        "pwhl_logo": pwhl_logo,
    }


def _slide4_data(results: dict, pwhl_logo: str | None) -> dict:
    return {
        "events":    results.get("pull_scored_events", []),
        "pwhl_logo": pwhl_logo,
    }


# ── Core renderer ─────────────────────────────────────────────────────────────

def render_slide(template_name: str, data: dict, output_path: Path) -> Path:
    """Render a Jinja2 HTML template to a 1080×1920 PNG via Playwright."""
    env  = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    tmpl = env.get_template(template_name)
    html = tmpl.render(**data)

    # Write temp HTML file next to output
    html_path = output_path.parent / f"_render_{template_name}"
    html_path.write_text(html, encoding="utf-8")

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page    = browser.new_page(viewport={"width": 1080, "height": 1920})
        page.goto(f"file://{html_path.resolve()}")
        page.wait_for_timeout(900)
        page.screenshot(path=str(output_path), full_page=False)
        browser.close()

    html_path.unlink(missing_ok=True)
    print(f"  ✅ {output_path.name}")
    return output_path


# ── Public entry point ────────────────────────────────────────────────────────

def render_all(results: dict, out_dir: Path | None = None) -> list[Path]:
    """
    Render all five empty net analysis slides.

    Args:
        results:  Dict returned by empty_net_analysis.analyze_games().
        out_dir:  Output directory; defaults to render/output/.

    Returns:
        List of output PNG paths.
    """
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    pwhl_logo = _pwhl_logo_uri()

    slides = [
        ("en_slide0.html", "en_slide0_overall.png",  _slide0_data(results, pwhl_logo)),
        ("en_slide1.html", "en_slide1_scored.png",   _slide1_data(results, pwhl_logo)),
        ("en_slide2.html", "en_slide2_allowed.png",  _slide2_data(results, pwhl_logo)),
        ("en_slide3.html", "en_slide3_timing.png",   _slide3_data(results, pwhl_logo)),
    ]

    print("\n🎬 Rendering Empty Net Analysis slides...")
    outputs = []
    for tmpl, fname, data in slides:
        path = out_dir / fname
        render_slide(tmpl, data, path)
        outputs.append(path)

    print(f"\n✨ Done — {len(outputs)} slides saved to {out_dir}")
    return outputs
