"""
Test tweet generation without using API credits
"""

from config import AI_PROVIDER
import config

# Now import the other modules (they'll use test mode)
from message_gen import generate_tweet_drafts

# TODO #23: Create fake game analysis data for testing
fake_analysis = {
    'game_info': {
        'game_id': '999',
        'date': '2025-12-26',
        'home_team': 'BOS',
        'visitor_team': 'MIN',
        'home_score': 4,
        'visitor_score': 3,
        'winner': 'BOS',
        'venue': 'Test Arena'
    },
    'hot_players': [
        {
            'name': 'Test Player',
            'team': 'BOS',
            'goals': 2,
            'assists': 1,
            'points': 3,
            'shots': 5,
            'highlights': ['2G', '1A', '+2']
        }
    ],
    'hot_goalies': [
        {
            'name': 'Test Goalie',
            'team': 'BOS',
            'saves': 32,
            'save_pct': 91.4,
            'goals_against': 3,
            'time': '60:00',
            'highlights': ['32 saves']
        }
    ]
}

# TODO #24: Test the generation
print("🧪 Testing tweet generation...")
drafts = generate_tweet_drafts(fake_analysis)

# Print results
for draft in drafts:
    print(f"\n{draft['type']}:")
    print(draft['tweet'])