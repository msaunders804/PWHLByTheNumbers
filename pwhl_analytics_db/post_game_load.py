#!/usr/bin/env python3
"""
Post-Game Load Script
Loads the most recently completed game into the database
"""

import sys
import os

# Add pwhl_analytics_db to path
script_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(script_dir, 'pwhl_analytics_db')
sys.path.insert(0, db_path)

from fetch_data import fetch_season_schedule
from load_data import load_game_data, load_teams
from db_queries import check_game_exists_in_db
from datetime import datetime


def load_most_recent_game(season_id=8):
    """
    Find and load the most recent completed game from the API

    Args:
        season_id: Season ID to check (default 8 for current season)

    Returns:
        Game ID if successful, None otherwise
    """
    print("=" * 60)
    print("POST-GAME LOAD - Most Recent Completed Game")
    print("=" * 60)

    try:
        # Fetch schedule from API
        print(f"\n📡 Fetching schedule for season {season_id}...")
        schedule_data = fetch_season_schedule(season_id)
        games = schedule_data['SiteKit']['Schedule']

        # Filter for completed games
        completed_games = [g for g in games if g['game_status'] == 'Final']

        if not completed_games:
            print("❌ No completed games found in schedule")
            return None

        # Sort by date (most recent first)
        completed_games.sort(key=lambda x: x['date_played'], reverse=True)
        most_recent = completed_games[0]

        game_id = int(most_recent['id'])
        game_date = most_recent['date_played']
        home_team = most_recent['home_team_city']
        away_team = most_recent['visiting_team_city']

        print(f"\n✓ Found most recent game:")
        print(f"  Game ID: {game_id}")
        print(f"  Date: {game_date}")
        print(f"  Matchup: {away_team} @ {home_team}")
        print(f"  Score: {most_recent['visiting_goal_count']}-{most_recent['home_goal_count']}")

        # Check if already in database
        if check_game_exists_in_db(game_id):
            print(f"\n⚠️  Game {game_id} already exists in database")

            # Ask user if they want to reload
            response = input("Reload anyway? (y/n): ").strip().lower()
            if response != 'y':
                print("✓ Skipping reload - game already in database")
                print(f"\n💡 Ready to generate tweets: python message_gen.py {game_id}")
                return game_id

        # Ensure teams are loaded
        print(f"\n📥 Ensuring teams are loaded for season {season_id}...")
        load_teams(season_id)

        # Load the game
        print(f"\n📥 Loading game {game_id} from API...")
        load_game_data(game_id)

        print(f"\n✅ Successfully loaded game {game_id}!")
        print(f"\n💡 Next step: python message_gen.py {game_id}")

        return game_id

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    # Check for optional season ID argument
    season_id = 8  # Default to current season

    if len(sys.argv) > 1:
        try:
            season_id = int(sys.argv[1])
            print(f"Using season ID: {season_id}")
        except ValueError:
            print(f"Invalid season ID: {sys.argv[1]}")
            print("Usage: python post_game_load.py [season_id]")
            sys.exit(1)

    game_id = load_most_recent_game(season_id)

    if game_id:
        print("\n" + "=" * 60)
        print("✅ COMPLETE!")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("❌ FAILED")
        print("=" * 60)
        sys.exit(1)
