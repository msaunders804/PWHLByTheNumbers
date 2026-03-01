#!/usr/bin/env python3
"""
Quick test to check if game 241 is available in the API
"""

import sys
import os

# Add pwhl_analytics_db to path
script_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(script_dir, 'pwhl_analytics_db')
sys.path.insert(0, db_path)

from fetch_data import fetch_game_summary
import json

game_id = 241

print(f"Testing game {game_id}...")
print("=" * 60)

try:
    data = fetch_game_summary(game_id)

    if 'GC' in data and 'Gamesummary' in data['GC']:
        summary = data['GC']['Gamesummary']
        meta = summary['meta']

        print("✓ Game data found!")
        print(f"\nGame ID: {meta['id']}")
        print(f"Date: {meta['date_played']}")
        print(f"Home Team: {meta.get('home_team', 'N/A')} (ID: {meta.get('home_team', 'N/A')})")
        print(f"Away Team: {meta.get('visiting_team', 'N/A')} (ID: {meta.get('visiting_team', 'N/A')})")
        print(f"Score: {meta.get('visiting_goal_count', 'N/A')}-{meta.get('home_goal_count', 'N/A')}")
        print(f"Final: {meta.get('final', 'N/A')}")
        print(f"Attendance: {meta.get('attendance', 'N/A')}")
        print(f"Venue: {summary.get('venue', 'N/A')}")

        print("\n" + "=" * 60)
        print("✓ Game is available in API and ready to load!")

        # Save full response for debugging
        with open('test_game_241_response.json', 'w') as f:
            json.dump(data, f, indent=2)
        print("Full API response saved to: test_game_241_response.json")

    else:
        print("❌ Unexpected API response structure")
        print(json.dumps(data, indent=2))

except Exception as e:
    print(f"❌ Error fetching game: {e}")
    import traceback
    traceback.print_exc()
