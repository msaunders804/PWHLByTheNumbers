import json
import glob

all_players = []

# Read all team files
for filepath in sorted(glob.glob('raw_data/temp/team_*.json')):
    print(f"Reading {filepath}...")
    with open(filepath, 'r') as f:
        data = json.load(f)
        # Extract roster array from each file
        if 'SiteKit' in data and 'Roster' in data['SiteKit']:
            roster = data['SiteKit']['Roster']
            # Filter out staff (last item is sometimes staff list)
            players = [p for p in roster if isinstance(p, dict) and 'player_id' in p]
            all_players.extend(players)
            print(f"  Found {len(players)} players")

# Save combined file
output = {
    'players': all_players,
    'total_count': len(all_players)
}

with open('raw_data/roster.json', 'w') as f:
    json.dump(output, f, indent=2)

print(f"\n✅ Combined {len(all_players)} players into raw_data/roster.json")

# Create clean metadata CSV
import pandas as pd

player_data = []
for player in all_players:
    player_data.append({
        'player_id': player['player_id'],
        'first_name': player['first_name'],
        'last_name': player['last_name'],
        'name': player['name'],
        'team_id': player['latest_team_id'],
        'team_name': player['team_name'],
        'position': player['position'],
        'jersey_number': player['tp_jersey_number'],
        'height': player.get('height', ''),
        'birthdate': player.get('birthdate', ''),
        'hometown': player.get('hometown', ''),
        'image_url': player['player_image']
    })

df = pd.DataFrame(player_data)
df.to_csv('metadata/player_metadata.csv', index=False)
print(f"✅ Created metadata/player_metadata.csv with {len(df)} players")