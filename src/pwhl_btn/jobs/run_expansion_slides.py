"""
run_expansion_slides.py — Render expansion city slides for the video.

Default renders: cover + top 5 + St. Louis + methodology (8 slides total).

Usage:
    python -m pwhl_btn.jobs.run_expansion_slides
    python -m pwhl_btn.jobs.run_expansion_slides --ranks 1 2 3
    python -m pwhl_btn.jobs.run_expansion_slides --all
    python -m pwhl_btn.jobs.run_expansion_slides --no-cover --no-methodology
"""
from __future__ import annotations

import argparse
from pathlib import Path

from pwhl_btn.analytics.expansion import score_cities
from pwhl_btn.render.expansion_render import (
    render_expansion_cover,
    render_expansion_city,
    render_expansion_honorable_mention,
    render_expansion_rankings,
    render_expansion_surprises,
    render_expansion_methodology,
)

OUTPUT_DIR    = Path(__file__).resolve().parents[3] / "render" / "output"
DEFAULT_RANKS = {1, 2, 3, 4, 5}
BONUS_CITIES  = {"st. louis"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Render PWHL expansion city slides")
    parser.add_argument("--no-cover",       action="store_true", help="Skip cover slide")
    parser.add_argument("--no-methodology", action="store_true", help="Skip methodology slide")
    parser.add_argument("--honorable-mention", action="store_true", help="Render only the honorable mention slide")
    parser.add_argument("--surprises",         action="store_true", help="Render only the surprises slide")
    parser.add_argument("--rankings",          action="store_true", help="Render only the final rankings slide")
    parser.add_argument("--ranks",          type=int, nargs="+", help="Specific rank numbers to render")
    parser.add_argument("--all",            action="store_true", help="Render all scored cities")
    args = parser.parse_args()

    print("\n  Loading expansion scores...")
    all_cities = score_cities()
    total = len(all_cities)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.rankings:
        print(f"  Rendering rankings slide  ->  {OUTPUT_DIR}\n")
        render_expansion_rankings(all_cities, out_dir=OUTPUT_DIR)
        print(f"\n  Done — 1 slide saved")
        return

    if args.surprises:
        print(f"  Rendering surprises slide  ->  {OUTPUT_DIR}\n")
        render_expansion_surprises(out_dir=OUTPUT_DIR)
        print(f"\n  Done — 1 slide saved")
        return

    if args.honorable_mention:
        print(f"  Rendering honorable mention slide  ->  {OUTPUT_DIR}\n")
        render_expansion_honorable_mention(all_cities, out_dir=OUTPUT_DIR)
        print(f"\n  Done — 1 slide saved")
        return

    if args.all:
        cities_to_render = all_cities
    elif args.ranks:
        cities_to_render = [c for c in all_cities if c["rank"] in args.ranks]
    else:
        cities_to_render = [
            c for c in all_cities
            if c["rank"] in DEFAULT_RANKS or c["city"].lower() in BONUS_CITIES
        ]

    for c in cities_to_render:
        c["total"] = total

    n_slides = len(cities_to_render) + (0 if args.no_cover else 1) + (0 if args.no_methodology else 1)
    print(f"  Rendering {n_slides} slide(s)  ->  {OUTPUT_DIR}\n")

    outputs: list[Path] = []

    if not args.no_cover:
        outputs.append(render_expansion_cover(city_count=total, out_dir=OUTPUT_DIR))

    for c in cities_to_render:
        outputs.append(render_expansion_city(c, out_dir=OUTPUT_DIR))

    if not args.no_methodology:
        outputs.append(render_expansion_methodology(out_dir=OUTPUT_DIR))

    print(f"\n  Done — {len(outputs)} slide(s) saved")


if __name__ == "__main__":
    main()
