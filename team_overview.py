import pandas as pd
import json
import sys

def load_data():
    """Load all necessary data files"""
    # Load skaters
    with open('raw_data/skaters.json', 'r', encoding='utf-8-sig') as f:
        skaters_data = json.load(f)
    
    # Load goalies
    with open('raw_data/goalies.json', 'r', encoding='utf-8-sig') as f:
        goalies_data = json.load(f)
    
    # Load standings
    with open('raw_data/standings.json', 'r', encoding='utf-8-sig') as f:
        standings_data = json.load(f)
    
    return skaters_data, goalies_data, standings_data

def parse_skaters(skaters_data):
    """Parse skater statistics"""
    players = []
    
    # Navigate to data in sections
    for section in skaters_data.get('sections', []):
        for player_data in section.get('data', []):
            row = player_data.get('row', {})
            players.append({
                'name': row.get('name', 'Unknown'),
                'team': row.get('team_code', 'Unknown'),
                'position': row.get('position', 'F'),
                'games_played': int(row.get('games_played', 0)),
                'goals': int(row.get('goals', 0)),
                'assists': int(row.get('assists', 0)),
                'points': int(row.get('points', 0)),
                'plus_minus': int(row.get('plus_minus', 0)),
                'shots': int(row.get('shots', 0)),
                'shooting_pct': float(row.get('shooting_percentage', 0))
            })
    
    return pd.DataFrame(players)

def parse_goalies(goalies_data):
    """Parse goalie statistics"""
    players = []
    
    # Navigate to data in sections
    for section in goalies_data.get('sections', []):
        for player_data in section.get('data', []):
            row = player_data.get('row', {})
            players.append({
                'name': row.get('name', 'Unknown'),
                'team': row.get('team_code', 'Unknown'),
                'games_played': int(row.get('games_played', 0)),
                'wins': int(row.get('wins', 0)),
                'save_pct': float(row.get('save_percentage', 0)),
                'gaa': float(row.get('goals_against_average', 0)),
                'shutouts': int(row.get('shutouts', 0))
            })
    
    return pd.DataFrame(players)

def get_team_overview(team_code, skaters_df, goalies_df):
    """Generate team overview statistics"""
    team_code = team_code.upper()
    
    # Filter for specific team
    team_skaters = skaters_df[skaters_df['team'] == team_code].copy()
    team_goalies = goalies_df[goalies_df['team'] == team_code].copy()
    
    if team_skaters.empty:
        print(f"❌ No data found for team: {team_code}")
        print(f"Available teams: {sorted(skaters_df['team'].unique())}")
        return None
    
    # Filter for minimum games played
    min_games = 3
    team_skaters = team_skaters[team_skaters['games_played'] >= min_games]
    team_goalies = team_goalies[team_goalies['games_played'] >= min_games]
    
    overview = {
        'team': team_code,
        'total_players': len(team_skaters) + len(team_goalies)
    }
    
    # Highest Scorer (Points)
    if not team_skaters.empty:
        top_scorer = team_skaters.nlargest(1, 'points').iloc[0]
        overview['top_scorer'] = {
            'name': top_scorer['name'],
            'points': top_scorer['points'],
            'goals': top_scorer['goals'],
            'assists': top_scorer['assists'],
            'games': top_scorer['games_played']
        }
        
        # Most Goals
        top_goal_scorer = team_skaters.nlargest(1, 'goals').iloc[0]
        overview['top_goal_scorer'] = {
            'name': top_goal_scorer['name'],
            'goals': top_goal_scorer['goals'],
            'games': top_goal_scorer['games_played']
        }
        
        # Most Assists
        top_assist = team_skaters.nlargest(1, 'assists').iloc[0]
        overview['top_assists'] = {
            'name': top_assist['name'],
            'assists': top_assist['assists'],
            'games': top_assist['games_played']
        }
        
        # Best Defender (by +/-)
        best_defender = team_skaters.nlargest(1, 'plus_minus').iloc[0]
        overview['best_defender'] = {
            'name': best_defender['name'],
            'plus_minus': best_defender['plus_minus'],
            'position': best_defender['position'],
            'games': best_defender['games_played']
        }
    
    # Best Goalie
    if not team_goalies.empty:
        best_goalie = team_goalies.nlargest(1, 'save_pct').iloc[0]
        overview['best_goalie'] = {
            'name': best_goalie['name'],
            'save_pct': best_goalie['save_pct'],
            'gaa': best_goalie['gaa'],
            'wins': best_goalie['wins'],
            'games': best_goalie['games_played']
        }
    
    return overview

def print_overview(overview):
    """Pretty print team overview"""
    if not overview:
        return
    
    print(f"\n{'='*60}")
    print(f"  {overview['team']} TEAM OVERVIEW")
    print(f"{'='*60}\n")
    
    if 'top_scorer' in overview:
        print(f"🏆 HIGHEST SCORER (Points)")
        s = overview['top_scorer']
        print(f"   {s['name']}: {s['points']} pts ({s['goals']}G + {s['assists']}A) in {s['games']} GP")
        print()
    
    if 'top_goal_scorer' in overview:
        print(f"⚽ MOST GOALS")
        g = overview['top_goal_scorer']
        print(f"   {g['name']}: {g['goals']} goals in {g['games']} GP")
        print()
    
    if 'top_assists' in overview:
        print(f"🎯 MOST ASSISTS")
        a = overview['top_assists']
        print(f"   {a['name']}: {a['assists']} assists in {a['games']} GP")
        print()
    
    if 'best_defender' in overview:
        print(f"🛡️  BEST DEFENDER (+/-)")
        d = overview['best_defender']
        plus_minus_str = f"+{d['plus_minus']}" if d['plus_minus'] >= 0 else str(d['plus_minus'])
        print(f"   {d['name']}: {plus_minus_str} ({d['position']}) in {d['games']} GP")
        print()
    
    if 'best_goalie' in overview:
        print(f"🥅 TOP GOALIE")
        g = overview['best_goalie']
        print(f"   {g['name']}: {g['save_pct']:.3f} SV% | {g['gaa']:.2f} GAA | {g['wins']}W in {g['games']} GP")
        print()
    
    print(f"{'='*60}\n")

def main():
    # Get team code from command line or prompt
    if len(sys.argv) > 1:
        team_code = sys.argv[1]
    else:
        print("Available teams: BOS, MTL, TOR, MIN, OTT, NY, SEA, VAN")
        team_code = input("Enter team code: ").strip()
    
    print("Loading data...")
    skaters_data, goalies_data, standings_data = load_data()
    
    print("Parsing skaters...")
    skaters_df = parse_skaters(skaters_data)
    print(f"  Found {len(skaters_df)} skaters")
    
    print("Parsing goalies...")
    goalies_df = parse_goalies(goalies_data)
    print(f"  Found {len(goalies_df)} goalies")
    
    print(f"Generating overview for {team_code}...")
    overview = get_team_overview(team_code, skaters_df, goalies_df)
    
    if overview:
        print_overview(overview)

if __name__ == "__main__":
    main()