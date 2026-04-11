"""
run_underrated_player.py — "The Most Underrated Player Nobody Talks About"

CLI report identifying the top 3 underrated non-MIN skaters with full
scoring breakdown and a ready-to-use TikTok reasoning hook for each.

Usage:
    python -m pwhl_btn.jobs.run_underrated_player
    python -m pwhl_btn.jobs.run_underrated_player --top 5
"""

import argparse
from pwhl_btn.analytics.underrated import get_top_underrated, SEASON_ID, EXCLUDE_TEAM


def _bar(score: float, lo: float = -2.0, hi: float = 2.0, width: int = 20) -> str:
    """Simple ASCII bar for a z-score."""
    pct   = max(0.0, min(1.0, (score - lo) / (hi - lo)))
    filled = round(pct * width)
    return "[" + "█" * filled + "░" * (width - filled) + "]"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--top", type=int, default=3, help="Number of players to show")
    args = parser.parse_args()

    print(f"\n  Loading skater data — Season {SEASON_ID} (excluding {EXCLUDE_TEAM})...")
    players = get_top_underrated(top_n=args.top)

    if not players:
        print("  No qualified skaters found.")
        return

    print(f"\n{'=' * 72}")
    print(f"  MOST UNDERRATED PLAYERS — Season {SEASON_ID}  (non-{EXCLUDE_TEAM})")
    print(f"{'=' * 72}")

    for p in players:
        print(f"\n  #{p['rank']}  {p['name']}  —  {p['team_code']}"
              f"  (Underrated Score: {p['underrated_score']:+.3f})")
        print(f"  {'─' * 60}")

        # Core stats
        print(f"  {'GP':<12} {int(p['gp'])}")
        print(f"  {'G-A-PTS':<12} {int(p['goals'])}-{int(p['assists'])}-{int(p['points'])}")
        print(f"  {'Pts/Game':<12} {p['pts_pg']:.3f}")
        print(f"  {'P/60':<12} {p['p60']:.2f}"
              + (f"  (avg TOI: {int(p['avg_toi_seconds'] or 0)//60}:{int(p['avg_toi_seconds'] or 0)%60:02d}/game)"
                 if p['avg_toi_seconds'] else "  (no TOI data)"))
        print(f"  {'Shots/Game':<12} {p['shots_pg']:.2f}  (sh%: {p['sh_pct']:.1%})")
        print(f"  {'+/- per GP':<12} {p['pm_pg']:+.2f}")
        print(f"  {'Team Rank':<12} #{p['team_position']} in standings")
        print(f"  {'Top Scorer?':<12} {'No — flying under the radar' if not p['is_top_scorer'] else 'Yes'}")

        # Score breakdown
        print(f"\n  Score pillars:")
        print(f"    P/60      {_bar(p['p60'],   0, 5)}  {p['p60']:.2f} pts/60")
        print(f"    Shots/GP  {_bar(p['shots_pg'], 0, 6)}  {p['shots_pg']:.2f}/game")
        print(f"    Sh%       {_bar(p['sh_pct'],   0, 0.25)}  {p['sh_pct']:.1%}")
        print(f"    +/- /GP   {_bar(p['pm_pg'],  -1, 1)}  {p['pm_pg']:+.2f}")
        print(f"    Obscurity {_bar(p['obscurity_bonus'], 0, 1.5)}  bonus: {p['obscurity_bonus']:.1f}")

        # TikTok hook
        print(f"\n  TIKTOK HOOK:")
        print(f"  \"{p['name']} might be the most underrated player in the PWHL")
        print(f"   right now and nobody is talking about her.\"")
        print()
        # Wrap reasoning at ~65 chars
        words   = p["reasoning"].split()
        line    = "  "
        for word in words:
            if len(line) + len(word) + 1 > 67:
                print(line)
                line = "  " + word + " "
            else:
                line += word + " "
        if line.strip():
            print(line)
        print(f"\n  \"Who do YOU think is the most underrated player this season? 👇\"")

    print(f"\n{'=' * 72}\n")


if __name__ == "__main__":
    main()
