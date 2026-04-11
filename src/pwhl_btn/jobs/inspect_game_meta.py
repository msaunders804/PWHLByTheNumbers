"""
inspect_game_meta.py — Print the raw meta keys from a gamesummary API response.

Usage:
    python -m pwhl_btn.jobs.inspect_game_meta
    python -m pwhl_btn.jobs.inspect_game_meta --game 1234
"""

import argparse
import json
from pwhl_btn.jobs.backfill import fetch_schedule, fetch_game, SEASON_ID


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", type=int, help="Specific game ID to inspect")
    args = parser.parse_args()

    if args.game:
        game_id = args.game
    else:
        print(f"Fetching schedule to find a completed game...")
        schedule = fetch_schedule(SEASON_ID)
        completed = [g for g in schedule
                     if str(g.get("game_status", "")).lower() == "final"
                     or str(g.get("status", "")) == "4"
                     or str(g.get("final", "0")) == "1"]
        if not completed:
            print("No completed games found.")
            return
        game_id = int(completed[0]["id"])

    print(f"\nFetching gamesummary for game {game_id}...")
    gs = fetch_game(game_id)

    print(f"\n--- top-level keys ---")
    for k, v in gs.items():
        if isinstance(v, dict):
            print(f"  {k!r:30s} => dict  ({list(v.keys())})")
        elif isinstance(v, list):
            print(f"  {k!r:30s} => list  (len={len(v)})")
        else:
            print(f"  {k!r:30s} = {v!r}")

    # Look for anything that smells like a venue/arena name
    print(f"\n--- venue/location candidates (all keys containing 'venue', 'arena', 'location', 'facility', 'rink') ---")
    def _search(obj, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                _search(v, f"{path}.{k}" if path else k)
        elif isinstance(obj, list):
            for i, item in enumerate(obj[:3]):  # only first 3 items of lists
                _search(item, f"{path}[{i}]")
        else:
            key_lower = path.split(".")[-1].split("[")[0].lower()
            if any(x in key_lower for x in ("venue", "arena", "location", "facility", "rink")):
                print(f"  {path:60s} = {obj!r}")

    _search(gs)

    print(f"\n--- periods ---")
    import json
    print(json.dumps(gs.get("periods", {}), indent=2))

    print(f"\n--- goalsByPeriod ---")
    print(json.dumps(gs.get("goalsByPeriod", {}), indent=2))

    print(f"\n--- goals[0] (first goal, all fields) ---")
    goals = gs.get("goals", [])
    if goals:
        print(json.dumps(goals[0], indent=2))
    else:
        print("  (no goals)")


if __name__ == "__main__":
    main()
