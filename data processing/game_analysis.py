#!/usr/bin/env python3
"""
PWHL Game Analysis Script
Analyzes completed games to identify hot players and key storylines
"""

import json
import requests
from datetime import datetime
from typing import Dict, List, Tuple

# API Configuration
BASE_URL = "https://lscluster.hockeytech.com/feed/"
API_KEY = "446521baf8c38984"
CLIENT_CODE = "pwhl"

# Team colors for formatting
TEAM_COLORS = {
    'BOS': '#000000',
    'MTL': '#862633',
    'TOR': '#00205B',
    'MIN': '#154734',
    'OTT': '#C8102E',
    'NY': '#6CACE4',
    'SEA': '#0C4C8A',
    'VAN': '#FFB81C'
}

def get_recent_completed_games(num_games=5):
    """Fetch recent completed games from schedule"""
    params = {
        'feed': 'modulekit',
        'view': 'schedule',
        'key': API_KEY,
        'fmt': 'json',
        'client_code': CLIENT_CODE,
        'lang': 'en',
        'season_id': '5',
        'team_id': '',
        'league_code': '',
        'fmt': 'json'
    }
    
    try:
        response = requests.get(BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        
        # Remove JavaScript wrapper if present
        text = response.text
        if text.startswith('angular.callbacks'):
            text = text[text.find('(')+1:text.rfind(')')]
        
        data = json.loads(text)
        
        # Find completed games
        completed_games = []
        if 'SiteKit' in data and 'Scorebar' in data['SiteKit']:
            for game in data['SiteKit']['Scorebar']:
                # GameStatus: 1=Scheduled, 2=Live, 3=Pre-game, 4=Final
                if game.get('GameStatus') == '4' and game.get('ID'):
                    completed_games.append({
                        'game_id': game['ID'],
                        'date': game.get('Date', ''),
                        'home_team': game.get('HomeCode', ''),
                        'visitor_team': game.get('VisitorCode', ''),
                        'home_score': game.get('HomeGoals', 0),
                        'visitor_score': game.get('VisitorGoals', 0)
                    })
        
        # Return most recent completed games
        return completed_games[:num_games]
    
    except Exception as e:
        print(f"❌ Error fetching schedule: {e}")
        return []

def get_game_details(game_id):
    """Fetch detailed game summary including player stats"""
    params = {
        'feed': 'gc',
        'tab': 'gamesummary',
        'game_id': game_id,
        'key': API_KEY,
        'client_code': CLIENT_CODE,
        'fmt': 'json'
    }
    
    try:
        response = requests.get(BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    
    except Exception as e:
        print(f"❌ Error fetching game {game_id}: {e}")
        return None

def analyze_player_performance(player, position):
    """Determine if a player had a hot game"""
    highlights = []
    
    # Skip goalies - they're analyzed separately
    if position == 'G':
        return None
    
    goals = int(player.get('goals', 0))
    assists = int(player.get('assists', 0))
    points = goals + assists
    shots = int(player.get('shots', 0))
    plus_minus = player.get('plusminus', '0')
    
    # Convert plus_minus to int
    if plus_minus == '0' or plus_minus == 0:
        pm_value = 0
    else:
        try:
            pm_value = int(plus_minus.replace('+', ''))
        except:
            pm_value = 0
    
    # Hot player criteria
    is_hot = False
    
    # Multi-goal game
    if goals >= 2:
        highlights.append(f"{goals}G")
        is_hot = True
    elif goals == 1:
        highlights.append(f"{goals}G")
    
    # High assist game
    if assists >= 2:
        highlights.append(f"{assists}A")
        is_hot = True
    elif assists == 1:
        highlights.append(f"{assists}A")
    
    # Multi-point game
    if points >= 3:
        is_hot = True
    
    # High shot volume
    if shots >= 6:
        highlights.append(f"{shots} shots")
        is_hot = True
    
    # Dominant plus/minus
    if pm_value >= 3:
        highlights.append(f"+{pm_value}")
        is_hot = True
    elif pm_value <= -3:
        highlights.append(f"{pm_value}")
    
    # Power play goals
    ppg = int(player.get('power_play_goals', 0))
    if ppg > 0:
        highlights.append(f"{ppg}PPG")
    
    # Game winning goal
    gwg = int(player.get('game_winning_goal', 0))
    if gwg > 0:
        highlights.append("GWG")
        is_hot = True
    
    if not is_hot:
        return None
    
    return {
        'name': f"{player['first_name']} {player['last_name']}",
        'jersey': player['jersey_number'],
        'position': position,
        'goals': goals,
        'assists': assists,
        'points': points,
        'plus_minus': plus_minus,
        'shots': shots,
        'highlights': highlights
    }

def analyze_goalie_performance(goalie):
    """Analyze goalie performance"""
    saves = int(goalie.get('saves', 0))
    shots_against = int(goalie.get('shots_against', 0))
    goals_against = int(goalie.get('goals_against', 0))
    time_played = goalie.get('time', '0:00')
    
    # Calculate save percentage
    if shots_against > 0:
        save_pct = (saves / shots_against) * 100
    else:
        save_pct = 0
    
    # Hot goalie criteria
    is_hot = False
    highlights = []
    
    # High save count
    if saves >= 30:
        highlights.append(f"{saves} saves")
        is_hot = True
    
    # Elite save percentage (on sufficient shots)
    if shots_against >= 20 and save_pct >= 95.0:
        highlights.append(f"{save_pct:.1f}% SV%")
        is_hot = True
    
    # Shutout
    if goals_against == 0 and shots_against >= 15:
        highlights.append("SHUTOUT")
        is_hot = True
    
    if not is_hot:
        return None
    
    return {
        'name': f"{goalie['first_name']} {goalie['last_name']}",
        'jersey': goalie['jersey_number'],
        'position': 'G',
        'saves': saves,
        'shots_against': shots_against,
        'goals_against': goals_against,
        'save_pct': save_pct,
        'time': time_played,
        'highlights': highlights
    }

def analyze_game(game_data):
    """Analyze a complete game for hot players and storylines"""
    if not game_data or 'GC' not in game_data:
        return None
    
    gc = game_data['GC']['Gamesummary']
    meta = gc['meta']
    
    # Game info
    game_info = {
        'game_id': meta['id'],
        'date': meta['date_played'],
        'home_team': gc['home']['team_code'],
        'visitor_team': gc['visitor']['team_code'],
        'home_score': int(meta['home_goal_count']),
        'visitor_score': int(meta['visiting_goal_count']),
        'final_score': f"{meta['visiting_goal_count']}-{meta['home_goal_count']}",
        'venue': gc.get('venue', 'Unknown'),
        'attendance': meta.get('attendance', 'N/A')
    }
    
    # Determine winner
    if game_info['home_score'] > game_info['visitor_score']:
        game_info['winner'] = game_info['home_team']
        game_info['loser'] = game_info['visitor_team']
    else:
        game_info['winner'] = game_info['visitor_team']
        game_info['loser'] = game_info['home_team']
    
    # Analyze players
    hot_players = []
    
    # Home team skaters
    if 'home_team_lineup' in gc and 'players' in gc['home_team_lineup']:
        for player in gc['home_team_lineup']['players']:
            analysis = analyze_player_performance(player, player.get('position_str', ''))
            if analysis:
                analysis['team'] = game_info['home_team']
                hot_players.append(analysis)
    
    # Visitor team skaters
    if 'visitor_team_lineup' in gc and 'players' in gc['visitor_team_lineup']:
        for player in gc['visitor_team_lineup']['players']:
            analysis = analyze_player_performance(player, player.get('position_str', ''))
            if analysis:
                analysis['team'] = game_info['visitor_team']
                hot_players.append(analysis)
    
    # Analyze goalies
    hot_goalies = []
    
    # Home goalies
    if 'home_team_lineup' in gc and 'goalies' in gc['home_team_lineup']:
        for goalie in gc['home_team_lineup']['goalies']:
            if int(goalie.get('shots_against', 0)) > 0:  # Only analyze if they played
                analysis = analyze_goalie_performance(goalie)
                if analysis:
                    analysis['team'] = game_info['home_team']
                    hot_goalies.append(analysis)
    
    # Visitor goalies
    if 'visitor_team_lineup' in gc and 'goalies' in gc['visitor_team_lineup']:
        for goalie in gc['visitor_team_lineup']['goalies']:
            if int(goalie.get('shots_against', 0)) > 0:
                analysis = analyze_goalie_performance(goalie)
                if analysis:
                    analysis['team'] = game_info['visitor_team']
                    hot_goalies.append(analysis)
    
    # Period analysis
    period_analysis = {
        'shots': gc.get('shotsByPeriod', {}),
        'goals': gc.get('goalsByPeriod', {})
    }
    
    return {
        'game_info': game_info,
        'hot_players': hot_players,
        'hot_goalies': hot_goalies,
        'period_analysis': period_analysis,
        'mvps': gc.get('mvps', [])
    }

def format_game_summary(analysis):
    """Generate a social media-ready game summary"""
    if not analysis:
        return "No analysis available"
    
    info = analysis['game_info']
    
    # Header
    summary = []
    summary.append("=" * 60)
    summary.append(f"🏒 {info['visitor_team']} @ {info['home_team']} - FINAL: {info['final_score']}")
    summary.append(f"📅 {info['date']} | 📍 {info['venue']}")
    summary.append(f"🎫 Attendance: {info['attendance']}")
    summary.append("=" * 60)
    
    # Hot Players
    if analysis['hot_players']:
        summary.append("\n🔥 HOT PLAYERS:")
        # Sort by points
        sorted_players = sorted(analysis['hot_players'], 
                              key=lambda x: x['points'], 
                              reverse=True)
        
        for player in sorted_players[:5]:  # Top 5
            highlights_str = " | ".join(player['highlights'])
            summary.append(f"  • {player['name']} (#{player['jersey']} {player['team']}) - {highlights_str}")
    
    # Hot Goalies
    if analysis['hot_goalies']:
        summary.append("\n🥅 GOALIE PERFORMANCE:")
        for goalie in analysis['hot_goalies']:
            highlights_str = " | ".join(goalie['highlights'])
            summary.append(f"  • {goalie['name']} (#{goalie['jersey']} {goalie['team']}) - {highlights_str}")
    
    # Period breakdown
    if 'shots' in analysis['period_analysis']:
        summary.append("\n📊 SHOTS BY PERIOD:")
        shots = analysis['period_analysis']['shots']
        if 'visitor' in shots and 'home' in shots:
            summary.append(f"  Period 1: {info['visitor_team']} {shots['visitor'].get('1', 0)} - {shots['home'].get('1', 0)} {info['home_team']}")
            summary.append(f"  Period 2: {info['visitor_team']} {shots['visitor'].get('2', 0)} - {shots['home'].get('2', 0)} {info['home_team']}")
            summary.append(f"  Period 3: {info['visitor_team']} {shots['visitor'].get('3', 0)} - {shots['home'].get('3', 0)} {info['home_team']}")
            
            # Calculate totals
            v_total = sum(shots['visitor'].get(str(i), 0) for i in range(1, 4))
            h_total = sum(shots['home'].get(str(i), 0) for i in range(1, 4))
            summary.append(f"  TOTAL: {info['visitor_team']} {v_total} - {h_total} {info['home_team']}")
    
    summary.append("=" * 60)
    
    return "\n".join(summary)

def get_recent_completed_games_from_file(days_back=7):
    """Get completed games from the last N days from local schedule file"""
    from datetime import datetime, timedelta
    
    # Try multiple possible locations
    possible_paths = [
        'raw_data/schedule.json',
        '../raw_data/schedule.json',
        'schedule.json',
        '/mnt/user-data/uploads/schedule.json'
    ]
    
    schedule_data = None
    used_path = None
    
    for path in possible_paths:
        try:
            with open(path, 'r', encoding='utf-8-sig') as f:
                schedule_data = json.load(f)
                used_path = path
                break
        except FileNotFoundError:
            continue
        except Exception as e:
            print(f"  ⚠️  Error reading {path}: {e}")
            continue
    
    if not schedule_data:
        print("  ❌ Could not find schedule.json in any expected location")
        print("     Tried:", ', '.join(possible_paths))
        return []
    
    print(f"  ✓ Loaded from: {used_path}")
    
    try:
        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        completed_games = []
        if 'SiteKit' in schedule_data and 'Scorebar' in schedule_data['SiteKit']:
            for game in schedule_data['SiteKit']['Scorebar']:
                # GameStatus: 4=Final
                if game.get('GameStatus') == '4' and game.get('ID'):
                    game_date_str = game.get('Date', '')
                    
                    # Parse game date (format: YYYY-MM-DD)
                    try:
                        game_date = datetime.strptime(game_date_str, '%Y-%m-%d')
                        
                        # Only include games within the last N days
                        if game_date >= cutoff_date:
                            completed_games.append({
                                'game_id': game['ID'],
                                'date': game_date_str,
                                'date_obj': game_date,
                                'home_team': game.get('HomeCode', ''),
                                'visitor_team': game.get('VisitorCode', ''),
                                'home_score': game.get('HomeGoals', 0),
                                'visitor_score': game.get('VisitorGoals', 0)
                            })
                    except ValueError:
                        # Skip games with invalid dates
                        continue
        
        # Sort by date (most recent first)
        completed_games.sort(key=lambda x: x['date_obj'], reverse=True)
        
        # Remove date_obj (only needed for sorting)
        for game in completed_games:
            del game['date_obj']
        
        return completed_games
    
    except Exception as e:
        print(f"  ❌ Error parsing schedule: {e}")
        return []

def download_game_json(game_id, output_dir="raw_data/games"):
    """Download game JSON from API and save locally"""
    import os
    
    # Create directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Build URL
    url = f"{BASE_URL}?feed=gc&tab=gamesummary&game_id={game_id}&key={API_KEY}&client_code={CLIENT_CODE}&fmt=json"
    
    print(f"  📥 Downloading game {game_id} data...")
    print(f"  URL: {url}")
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # Save to file
        output_file = f"{output_dir}/game_{game_id}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(response.json(), f, indent=2)
        
        print(f"  ✓ Saved to: {output_file}")
        return response.json()
    
    except Exception as e:
        print(f"  ❌ Error downloading game {game_id}: {e}")
        return None

def main():
    """Main execution function"""
    import sys
    import os
    
    print("🏒 PWHL Game Analysis Tool")
    print("=" * 60)
    
    # MODE 1: Manual game analysis with provided JSON file
    if len(sys.argv) > 1 and len(sys.argv) <= 2:
        game_id = sys.argv[1]
        
        # Check if it's actually a mode flag
        if game_id in ['--auto', '-a', '--latest', '-l']:
            # Fall through to auto mode
            pass
        else:
            print(f"\n🎯 Manual Mode - Analyzing Game ID: {game_id}")
            print("⚠️  Please provide game JSON file")
            print(f"Usage: python3 game_analysis.py {game_id} <path_to_game_json>")
            return
    
    elif len(sys.argv) > 2:
        game_id = sys.argv[1]
        json_file = sys.argv[2]
        
        print(f"\n🎯 Manual Mode - Analyzing Game ID: {game_id}")
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                text = f.read()
            
            # Use raw decoder to handle potential extra characters
            decoder = json.JSONDecoder()
            game_data, _ = decoder.raw_decode(text)
            
            analysis = analyze_game(game_data)
            if analysis:
                print(format_game_summary(analysis))
                
                os.makedirs('outputs', exist_ok=True)
                
                # Save text summary
                output_file = f"outputs/game_analysis_{game_id}.txt"
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(format_game_summary(analysis))
                print(f"\n💾 Saved text summary to: {output_file}")
                
                # Save JSON data for tweet generation
                json_output_file = f"outputs/game_analysis_{game_id}.json"
                with open(json_output_file, 'w', encoding='utf-8') as f:
                    json.dump(analysis, f, indent=2)
                print(f"💾 Saved JSON data to: {json_output_file}")
            else:
                print("❌ Could not analyze game")
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
        return
    
    # MODE 2: AUTO MODE - Analyze most recent completed game
    print("\n🤖 AUTO MODE - Analyzing Most Recent Completed Game")
    print("-" * 60)
    
    # Get recent completed games from local file (last 7 days)
    print("\n📂 Reading schedule from local file (last 7 days)...")
    games = get_recent_completed_games_from_file(days_back=7)
    
    if not games:
        print("❌ No completed games found in schedule")
        print("\nℹ️  You can manually analyze a game with:")
        print("   python3 game_analysis.py <game_id> <path_to_game_json>")
        return
    
    # Get the most recent game
    most_recent = games[0]
    
    print(f"✓ Found {len(games)} completed game(s)")
    print(f"\n🎯 Most Recent: Game #{most_recent['game_id']}")
    print(f"   {most_recent['visitor_team']} @ {most_recent['home_team']}")
    print(f"   Final: {most_recent['visitor_score']}-{most_recent['home_score']}")
    print(f"   Date: {most_recent['date']}")
    
    # Check if we already have this game's JSON
    game_file = f"raw_data/games/game_{most_recent['game_id']}.json"
    
    if os.path.exists(game_file):
        print(f"\n📂 Found cached game data: {game_file}")
        try:
            with open(game_file, 'r', encoding='utf-8') as f:
                game_data = json.load(f)
        except Exception as e:
            print(f"  ⚠️  Error reading cached file: {e}")
            print("  Will try to download fresh data...")
            game_data = download_game_json(most_recent['game_id'])
    else:
        print(f"\n📡 Game data not cached, attempting download...")
        game_data = download_game_json(most_recent['game_id'])
    
    if not game_data:
        print("\n❌ Could not retrieve game data")
        print("\n💡 You can manually download and analyze:")
        print(f"   1. Download from: {BASE_URL}?feed=gc&tab=gamesummary&game_id={most_recent['game_id']}&key={API_KEY}&client_code={CLIENT_CODE}&fmt=json")
        print(f"   2. Save as: game_{most_recent['game_id']}.json")
        print(f"   3. Run: python3 game_analysis.py {most_recent['game_id']} game_{most_recent['game_id']}.json")
        return
    
    # Analyze the game
    print("\n🔍 Analyzing game...")
    analysis = analyze_game(game_data)
    
    if not analysis:
        print("❌ Could not analyze game")
        return
    
    # Display results
    print("\n" + format_game_summary(analysis))
    
    # Save to files (both text and JSON)
    os.makedirs('outputs', exist_ok=True)
    
    # Save text summary
    output_file = f"outputs/game_analysis_{most_recent['game_id']}.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(format_game_summary(analysis))
    
    print(f"\n💾 Saved text summary to: {output_file}")
    
    # Save JSON data for tweet generation
    json_output_file = f"outputs/game_analysis_{most_recent['game_id']}.json"
    with open(json_output_file, 'w', encoding='utf-8') as f:
        json.dump(analysis, f, indent=2)
    
    print(f"💾 Saved JSON data to: {json_output_file}")
    
    # TODO: Auto-update attendance records
    print("\n📊 Updating attendance records...")
    try:
        from attendance import add_game_attendance
        add_game_attendance(analysis)
    except Exception as e:
        print(f"  ⚠️  Could not update attendance: {e}")
    
    # Show next games info
    if len(games) > 1:
        print(f"\n📋 Other Recent Games:")
        for i, game in enumerate(games[1:4], 2):
            print(f"   {i}. Game #{game['game_id']}: {game['visitor_team']} @ {game['home_team']} - {game['visitor_score']}-{game['home_score']} ({game['date']})")
        print(f"\n💡 To analyze another game: python3 game_analysis.py <game_id> <json_file>")

if __name__ == "__main__":
    main()