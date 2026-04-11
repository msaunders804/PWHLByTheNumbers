"""
run_expansion_analysis.py — PWHL Expansion City Scorecard CLI

"I ran the numbers on where PWHL should expand — and the answer might surprise you."

Usage:
    python -m pwhl_btn.jobs.run_expansion_analysis
    python -m pwhl_btn.jobs.run_expansion_analysis --verbose
"""

import argparse
from pwhl_btn.analytics.expansion import score_cities

WEIGHTS = {
    "nhl_market":      ("NHL Market Depth",         "25%"),
    "tour_attendance": ("Takeover Tour Attendance",  "35%"),
    "womens_sports":   ("Women's Sports Viability",  "20%"),
    "arena_fit":       ("Arena Fit",                 "10%"),
    "geo_balance":     ("Geographic Balance",        "10%"),
}

MEDAL = {1: "🥇", 2: "🥈", 3: "🥉", 4: " #4", 5: " #5"}


def _bar(score: float, width: int = 15) -> str:
    filled = round((score / 10.0) * width)
    return "█" * filled + "░" * (width - filled)


def _score_block(pillar_scores: dict) -> str:
    lines = []
    for key, (label, weight) in WEIGHTS.items():
        s = pillar_scores.get(key, 0)
        lines.append(f"    {label:<30} {weight}  [{_bar(s)}]  {s:.1f}/10")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true",
                        help="Show notes for each metric")
    args = parser.parse_args()

    print("\n  Loading expansion data...")
    cities = score_cities()

    # ── Summary scorecard ──────────────────────────────────────────────────────
    print(f"\n{'=' * 72}")
    print(f"  PWHL EXPANSION SCORECARD")
    print(f"  Weights: NHL Mkt 25% | Tour Att 35% | Women's Sports 20% | Arena 10% | Geo 10%")
    print(f"{'=' * 72}")
    print(f"\n  {'RNK':<4}  {'CITY':<14}  {'NHL TEAM':<26}  "
          f"{'TOUR ATT':>10}  {'GAMES':>5}  {'SCORE':>7}")
    print(f"  {'─'*68}")

    for c in cities:
        medal    = MEDAL.get(c["rank"], f"#{c['rank']}")
        att_str  = f"{c['tour_avg_att']:,}" if c["tour_avg_att"] else "No data"
        games_str = f"({c['tour_game_count']}g)" if c["tour_game_count"] else "(—)"
        print(f"  {medal}    {c['city']:<14}  {c['nhl_team']:<26}  "
              f"{att_str:>10}  {games_str:>5}  {c['composite_score']:>6.3f}")

    # ── Detailed breakdown ─────────────────────────────────────────────────────
    print(f"\n{'─' * 72}")
    print(f"  DETAILED BREAKDOWN")
    print(f"{'─' * 72}")

    for c in cities:
        medal = MEDAL.get(c["rank"], f"#{c['rank']}")
        print(f"\n  {medal}  {c['city'].upper()}, {c['state_province']}  "
              f"—  Composite Score: {c['composite_score']:.3f}/10")
        print(f"      NHL partner: {c['nhl_team']}")
        if c["tour_avg_att"]:
            att_note = (f"avg {c['tour_avg_att']:,}"
                        + (f" across {c['tour_game_count']} games"
                           if c["tour_game_count"] > 1
                           else f" (1 game — {c['tour_total_att']:,} total)"))
            print(f"      Tour attendance: {att_note}")
        else:
            print(f"      Tour attendance: No Takeover Tour game on record")
        print()
        print(_score_block(c["pillar_scores"]))

        if args.verbose:
            print(f"\n      Notes:")
            print(f"        NHL:    {c['nhl_market_notes']}")
            print(f"        Women's: {c['womens_sports_notes']}")
            print(f"        Arena:  {c['arena_fit_notes']}")
            print(f"        Geo:    {c['geo_balance_notes']}")

        print(f"\n      TIKTOK HOOK: \"{c['narrative_hook']}\"")

    # ── TikTok script outline ──────────────────────────────────────────────────
    winner = cities[0]
    runner = cities[1]
    surprise = next((c for c in cities if c["city"] not in
                     ["Chicago", "Detroit"]), cities[2])  # find the "surprise" pick

    print(f"\n{'=' * 72}")
    print(f"  TIKTOK SCRIPT OUTLINE")
    print(f"{'=' * 72}")
    print(f"""
  HOOK:
  "I ran the numbers on where the PWHL should expand next —
   and the answer might actually surprise you."

  SETUP (3-4 seconds):
  "I scored every candidate city on 5 metrics that actually matter
   for a business decision — not just population, but revealed preference."

  REVEAL THE SCORECARD (show graphic, pan down):
  5. {cities[4]['city']} — {cities[4]['composite_score']:.2f}/10
  4. {cities[3]['city']} — {cities[3]['composite_score']:.2f}/10
  3. {cities[2]['city']} — {cities[2]['composite_score']:.2f}/10
  2. {runner['city']} — {runner['composite_score']:.2f}/10
  1. {winner['city']} — {winner['composite_score']:.2f}/10

  THE SURPRISE MOMENT:
  "{winner['narrative_hook']}"

  TOUR DATA CALLOUT:
  "This isn't a survey. This is {winner['tour_avg_att']:,} people
   showing up and paying — with no home team. That's revealed preference."

  CLOSER (comment bait):
  "The PWHL is east-heavy. One of these cities fixes that AND has
   the numbers to back it up. Which city do YOU think gets the next team? 👇"
""")

    print(f"{'=' * 72}\n")


if __name__ == "__main__":
    main()
