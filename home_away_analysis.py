"""
Quick analysis of home vs away team win rates in PWHL
Analyzes historical game data to determine if home ice advantage exists
"""

import sys
import os

# Add pwhl_analytics_db to path
script_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(script_dir, 'pwhl_analytics_db')
sys.path.insert(0, db_path)

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from db_models import Game, Team

# Database configuration
DATABASE_URL = 'postgresql://postgres:SecurePassword@localhost/pwhl_analytics'
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


def analyze_home_away_performance():
    """
    Analyze home vs away win rates across all completed games
    """
    session = Session()

    try:
        # Get all completed games
        games = session.query(Game).filter(
            Game.game_status == 'final',
            Game.home_score.isnot(None),
            Game.away_score.isnot(None)
        ).all()

        if not games:
            print("No completed games found in database")
            return

        # Track results
        total_games = len(games)
        home_wins = 0
        away_wins = 0
        ties = 0

        home_goals_total = 0
        away_goals_total = 0

        # Track by season
        season_stats = {}

        for game in games:
            # Count wins
            if game.home_score > game.away_score:
                home_wins += 1
            elif game.away_score > game.home_score:
                away_wins += 1
            else:
                ties += 1

            # Track goals
            home_goals_total += game.home_score
            away_goals_total += game.away_score

            # Track by season
            season = game.season_id
            if season not in season_stats:
                season_stats[season] = {
                    'games': 0,
                    'home_wins': 0,
                    'away_wins': 0,
                    'ties': 0,
                    'home_goals': 0,
                    'away_goals': 0
                }

            season_stats[season]['games'] += 1
            season_stats[season]['home_goals'] += game.home_score
            season_stats[season]['away_goals'] += game.away_score

            if game.home_score > game.away_score:
                season_stats[season]['home_wins'] += 1
            elif game.away_score > game.home_score:
                season_stats[season]['away_wins'] += 1
            else:
                season_stats[season]['ties'] += 1

        # Calculate percentages
        home_win_pct = (home_wins / total_games) * 100 if total_games > 0 else 0
        away_win_pct = (away_wins / total_games) * 100 if total_games > 0 else 0
        tie_pct = (ties / total_games) * 100 if total_games > 0 else 0

        avg_home_goals = home_goals_total / total_games if total_games > 0 else 0
        avg_away_goals = away_goals_total / total_games if total_games > 0 else 0

        # Print results
        print("=" * 60)
        print("PWHL HOME vs AWAY PERFORMANCE ANALYSIS")
        print("=" * 60)
        print()
        print(f"Total Games Analyzed: {total_games}")
        print()
        print("-" * 60)
        print("WIN RATES")
        print("-" * 60)
        print(f"Home Team Wins:  {home_wins:4d} ({home_win_pct:5.1f}%)")
        print(f"Away Team Wins:  {away_wins:4d} ({away_win_pct:5.1f}%)")
        if ties > 0:
            print(f"Ties:            {ties:4d} ({tie_pct:5.1f}%)")
        print()

        print("-" * 60)
        print("SCORING AVERAGES")
        print("-" * 60)
        print(f"Avg Home Team Goals: {avg_home_goals:.2f}")
        print(f"Avg Away Team Goals: {avg_away_goals:.2f}")
        print(f"Goal Differential:   {avg_home_goals - avg_away_goals:+.2f} (home advantage)")
        print()

        # Season breakdown
        print("-" * 60)
        print("BY SEASON BREAKDOWN")
        print("-" * 60)

        for season in sorted(season_stats.keys()):
            stats = season_stats[season]
            s_home_pct = (stats['home_wins'] / stats['games']) * 100 if stats['games'] > 0 else 0
            s_away_pct = (stats['away_wins'] / stats['games']) * 100 if stats['games'] > 0 else 0
            s_avg_home = stats['home_goals'] / stats['games'] if stats['games'] > 0 else 0
            s_avg_away = stats['away_goals'] / stats['games'] if stats['games'] > 0 else 0

            print(f"\nSeason {season}:")
            print(f"  Games: {stats['games']}")
            print(f"  Home Wins: {stats['home_wins']} ({s_home_pct:.1f}%)")
            print(f"  Away Wins: {stats['away_wins']} ({s_away_pct:.1f}%)")
            print(f"  Avg Goals: Home {s_avg_home:.2f} | Away {s_avg_away:.2f}")

        print()
        print("=" * 60)
        print("INTERPRETATION")
        print("=" * 60)

        # Determine if home advantage exists
        if home_win_pct > 52:  # More than random + small margin
            advantage_strength = "strong" if home_win_pct > 60 else "moderate"
            print(f"✓ {advantage_strength.upper()} HOME ICE ADVANTAGE detected")
            print(f"  Home teams win {home_win_pct - 50:.1f} percentage points above 50%")
        elif home_win_pct > 50:
            print("✓ SLIGHT HOME ICE ADVANTAGE detected")
            print(f"  Home teams win {home_win_pct - 50:.1f} percentage points above 50%")
        elif home_win_pct < 48:
            print("⚠ NO HOME ICE ADVANTAGE - Away teams winning more")
        else:
            print("≈ NO CLEAR ADVANTAGE - Roughly even split")

        print()
        print("For predictive modeling:")
        print(f"  - Baseline 'always pick home' accuracy: {home_win_pct:.1f}%")
        print(f"  - Your model should beat: {max(home_win_pct, away_win_pct):.1f}%")
        print("=" * 60)

    finally:
        session.close()


if __name__ == "__main__":
    analyze_home_away_performance()
