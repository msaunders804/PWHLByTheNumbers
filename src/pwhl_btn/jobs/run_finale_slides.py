"""
run_finale_slides.py — Render Season 8 Final Day game stakes slides.

Usage:
    python -m pwhl_btn.jobs.run_finale_slides
    python -m pwhl_btn.jobs.run_finale_slides --game 1   # MTL @ SEA only
"""
from __future__ import annotations
import argparse
from pathlib import Path
from pwhl_btn.render.finale_render import GAMES, render_game_slide, render_hook_slide, render_all

OUTPUT_DIR = Path(__file__).resolve().parents[3] / "render" / "output"


def main() -> None:
    parser = argparse.ArgumentParser(description="Season 8 finale game stakes slides")
    parser.add_argument("--game", type=int, choices=[1, 2, 3, 4],
                        help="Render a single game (1=MTL@SEA, 2=NY@BOS, 3=TOR@OTT, 4=MIN@VAN)")
    parser.add_argument("--hook", action="store_true", help="Render only the hook slide")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n  Season 8 Final Day — Game Stakes Slides")
    print(f"  Output -> {OUTPUT_DIR}\n")

    if args.hook:
        render_hook_slide(out_dir=OUTPUT_DIR)
    elif args.game:
        render_game_slide(GAMES[args.game - 1], out_dir=OUTPUT_DIR)
    else:
        render_all(out_dir=OUTPUT_DIR)

    print("\n  Done.")


if __name__ == "__main__":
    main()
