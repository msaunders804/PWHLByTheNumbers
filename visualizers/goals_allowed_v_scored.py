import pandas as pd
import matplotlib.pyplot as plt
import json

# Load standings data
with open('raw_data/standings.json', 'r', encoding='utf-8-sig') as f:
    data = json.load(f)

# Navigate to the actual team data
standings = data['SiteKit']['Statviewtype']

# Extract team data (skip first item which is header)
teams_data = []
for team in standings[1:]:  # Skip the first header row
    teams_data.append({
        'Team': team['team_code'],
        'Full Name': team['team_name'],
        'Goals For': int(team['goals_for']),
        'Goals Against': int(team['goals_against']),
        'Goal Diff': int(team['goals_diff']),
        'Points': int(team['points']),
        'Wins': int(team['wins'])
    })

df = pd.DataFrame(teams_data)

# Create visualization
plt.figure(figsize=(12, 8))
team_colors = {
    'BOS': '#000000',      # Black
    'MTL': '#862633',      # Burgundy
    'TOR': '#00205B',      # Blue
    'MIN': '#154734',      # Dark Green
    'OTT': '#C8102E',      # Red
    'NY': '#6CACE4',       # Light Blue
    'SEA': '#0C4C8A',      # Navy/Ocean Blue
    'VAN': '#FFB81C'       # Gold/Yellow
}
scatter = plt.scatter(df['Goals For'], df['Goals Against'], 
                     s=df['Points']*15, alpha=0.7, c=[team_colors[team] for team in df['Team']])

# Add team labels
for i, row in df.iterrows():
    plt.annotate(row['Team'], 
                (row['Goals For'], row['Goals Against']),
                fontsize=12, fontweight='bold',
                xytext=(5, 5), textcoords='offset points')

# Add reference lines
plt.axhline(df['Goals Against'].mean(), color='red', linestyle='--', 
           alpha=0.5, linewidth=2, label=f"Avg GA ({df['Goals Against'].mean():.1f})")
plt.axvline(df['Goals For'].mean(), color='blue', linestyle='--', 
           alpha=0.5, linewidth=2, label=f"Avg GF ({df['Goals For'].mean():.1f})")

# Quadrant labels
max_gf = df['Goals For'].max()
max_ga = df['Goals Against'].max()
avg_gf = df['Goals For'].mean()
avg_ga = df['Goals Against'].mean()


plt.xlabel('Goals For (Offense)', fontsize=12, fontweight='bold')
plt.ylabel('Goals Against (Defense)', fontsize=12, fontweight='bold')
plt.title('PWHL Team Performance: Offense vs Defense\n(Bubble size = Points)', 
         fontsize=14, fontweight='bold', pad=20)
plt.legend(loc='upper left', fontsize=10)
plt.grid(alpha=0.3, linestyle=':')
plt.tight_layout()

# Save
import os
os.makedirs('outputs', exist_ok=True)
plt.savefig('outputs/team_performance.png', dpi=300, bbox_inches='tight')
plt.show()

print("✅ Chart saved to outputs/team_performance.png")
print("\n📊 Quick Stats:")
print(df[['Team', 'Goals For', 'Goals Against', 'Goal Diff', 'Points']].to_string(index=False))