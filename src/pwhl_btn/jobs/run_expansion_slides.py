"""
run_expansion_slides.py — Render expansion city slides for the video.

Produces 1080x1920 PNGs:
  expansion_00_cover.png
  expansion_01_washington.png
  expansion_02_calgary.png
  expansion_03_denver.png
  expansion_04_detroit.png
  expansion_05_chicago.png
  expansion_06_st._louis.png   (bonus city)

Usage:
    python -m pwhl_btn.jobs.run_expansion_slides
    python -m pwhl_btn.jobs.run_expansion_slides --cities WAS CAL DEN  # by city prefix
    python -m pwhl_btn.jobs.run_expansion_slides --no-cover
"""
from __future__ import annotations

import argparse
from pathlib import Path

from pwhl_btn.analytics.expansion import score_cities
from pwhl_btn.render.expansion_render import render_expansion_cover, render_expansion_city

OUTPUT_DIR    = Path(__file__).resolve().parents[3] / "render" / "output"
DEFAULT_RANKS = {1, 2, 3, 4, 5}
BONUS_CITIES  = {"st. louis"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Render PWHL expansion city slides")
    parser.add_argument("--no-cover", action="store_true", help="Skip cover slide")
    parser.add_argument("--ranks",    type=int, nargs="+",
                        help="Specific rank numbers to render (default: 1-5 + St. Louis)")
    parser.add_argument("--all",      action="store_true", help="Render all scored cities")
    args = parser.parse_args()

    print("\n  Loading expansion scores...")
    all_cities = score_cities()
    total = len(all_cities)

    if args.all:
        cities_to_render = all_cities
    elif args.ranks:
        cities_to_render = [c for c in all_cities if c["rank"] in args.ranks]
    else:
        cities_to_render = [
            c for c in all_cities
            if c["rank"] in DEFAULT_RANKS or c["city"].lower() in BONUS_CITIES
        ]

    # Attach total for the rank display
    for c in cities_to_render:
        c["total"] = total

    print(f"  Rendering {len(cities_to_render)} city slide(s)"
          + (" + cover" if not args.no_cover else ""))
    print(f"  Output -> {OUTPUT_DIR}\n")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []

    if not args.no_cover:
        outputs.append(render_expansion_cover(city_count=total, out_dir=OUTPUT_DIR))

    for c in cities_to_render:
        outputs.append(render_expansion_city(c, out_dir=OUTPUT_DIR))

    print(f"\n  Done — {len(outputs)} slide(s) saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
