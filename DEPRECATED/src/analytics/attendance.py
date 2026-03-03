"""
PWHL Attendance Analysis
Tracks attendance trends and identifies high-attendance games
Imports historical data from API and maintains persistent records
"""

import json
import os
import requests
import time
from datetime import datetime, timedelta

# API Configuration
BASE_URL = "https://lscluster.hockeytech.com/feed/"
API_KEY = "446521baf8c38984"
CLIENT_CODE = "pwhl"

ATTENDANCE_FILE = "raw_data/attendance_records.json"

# ============================================================================
# CORE DATA MANAGEMENT
# ============================================================================

def load_attendance_records():
    """
    Load existing attendance records from file
    
    Returns:
        Dict with 'games' list and metadata
    """
    
    if not os.path.exists(ATTENDANCE_FILE):
        return {
            'games': [],
            'last_updated': None,
            'total_games': 0
        }
    
    with open(ATTENDANCE_FILE, 'r') as f:
        records = json.load(f)
    
    return records


def save_attendance_records(records):
    """
    Save attendance records to file
    
    Args:
        records: Dict with games list and metadata
    """
    
    # Update metadata
    records['last_updated'] = datetime.now().isoformat()
    records['total_games'] = len(records['games'])
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(ATTENDANCE_FILE), exist_ok=True)
    
    # Save to file
    with open(ATTENDANCE_FILE, 'w') as f:
        json.dump(records, f, indent=2)


# ============================================================================
# API DATA FETCHING
# ============================================================================

def get_all_completed_games_from_schedule():
    """
    Fetch all completed games from the schedule API
    
    Returns:
        List of game dicts with basic info
    """
    
    print("📡 Fetching schedule from API...")
    
    params = {
        'feed': 'modulekit',
        'view': 'scorebar',
        'key': API_KEY,
        'fmt': 'json',
        'client_code': CLIENT_CODE,
        'lang': 'en',
        'league_id': '1',
        'season_id': '8',  # Current season
        'numberofdaysahead': '0',
        'numberofdaysback': '365'  # Get last year of games
    }
    
    try:
        response = requests.get(BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        
        # Remove JavaScript wrapper if present
        text = response.text
        if text.startswith('angular.callbacks'):
            text = text[text.find('(')+1:text.rfind(')')]
        
        data = json.loads(text)
        
        # Extract completed games
        completed_games = []
        
        if 'SiteKit' in data and 'Scorebar' in data['SiteKit']:
            for game in data['SiteKit']['Scorebar']:
                # Only get completed games (GameStatus = 4)
                if game.get('GameStatus') == '4' and game.get('ID'):
                    completed_games.append({
                        'game_id': game['ID'],
                        'date': game.get('Date', ''),
                        'home_team': game.get('HomeCode', ''),
                        'visitor_team': game.get('VisitorCode', ''),
                        'home_score': game.get('HomeGoals', 0),
                        'visitor_score': game.get('VisitorGoals', 0)
                    })
        
        print(f"  ✓ Found {len(completed_games)} completed games")
        
        return completed_games
        
    except Exception as e:
        print(f"  ❌ Error fetching schedule: {e}")
        return []


def fetch_game_attendance_from_api(game_id):
    """
    Fetch attendance data for a single game from the API
    
    Args:
        game_id: Game ID to fetch
    
    Returns:
        Dict with attendance info, or None if error
    """
    
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
        game_data = response.json()
        
        # Extract attendance from game data
        if 'GC' not in game_data or 'Gamesummary' not in game_data['GC']:
            return None
        
        gc = game_data['GC']['Gamesummary']
        meta = gc['meta']
        
        # Parse attendance
        attendance_str = meta.get('attendance', '0')
        try:
            attendance = int(str(attendance_str).replace(',', ''))
        except:
            attendance = 0
        
        # Skip if no attendance
        if attendance == 0:
            return None
        
        # Build attendance record
        record = {
            'game_id': meta['id'],
            'date': meta['date_played'],
            'home_team': gc['home']['team_code'],
            'visitor_team': gc['visitor']['team_code'],
            'venue': gc.get('venue', 'Unknown'),
            'attendance': attendance,
            'final_score': f"{meta['visiting_goal_count']}-{meta['home_goal_count']}",
            'winner': gc['home']['team_code'] if int(meta['home_goal_count']) > int(meta['visiting_goal_count']) else gc['visitor']['team_code'],
            'added_at': datetime.now().isoformat()
        }
        
        return record
        
    except Exception as e:
        print(f"    ⚠️  Error fetching game {game_id}: {e}")
        return None


# ============================================================================
# IMPORT FUNCTIONS
# ============================================================================

def import_historical_attendance(max_games=None, delay=1.0):
    """
    Import attendance data for all completed games from API
    
    Args:
        max_games: Maximum number of games to import (None = all)
        delay: Delay between API calls in seconds (to avoid rate limits)
    
    Returns:
        Int - number of games imported
    """
    
    print("🔄 IMPORTING HISTORICAL ATTENDANCE DATA")
    print("=" * 60)
    print("⚠️  This may take a while on first run...")
    print()
    
    # Load existing records to avoid duplicates
    records = load_attendance_records()
    existing_ids = {g['game_id'] for g in records['games']}
    
    print(f"📊 Current records: {len(existing_ids)} games")
    
    # Get all completed games from schedule
    all_games = get_all_completed_games_from_schedule()
    
    if not all_games:
        print("❌ No games found in schedule")
        return 0
    
    # Filter out games we already have
    new_games = [g for g in all_games if g['game_id'] not in existing_ids]
    
    print(f"🆕 New games to import: {len(new_games)}")
    
    if not new_games:
        print("✅ All games already imported!")
        return 0
    
    # Limit if requested
    if max_games and len(new_games) > max_games:
        print(f"⚠️  Limiting import to {max_games} games (use --full for all)")
        new_games = new_games[:max_games]
    
    # Import each game
    imported_count = 0
    skipped_count = 0
    
    for i, game in enumerate(new_games, 1):
        game_id = game['game_id']
        
        print(f"[{i}/{len(new_games)}] Fetching game {game_id} "
              f"({game['visitor_team']} @ {game['home_team']})...", end=' ')
        
        # Fetch attendance data
        attendance_record = fetch_game_attendance_from_api(game_id)
        
        if attendance_record:
            # Add to records
            records['games'].append(attendance_record)
            imported_count += 1
            print(f"✓ {attendance_record['attendance']:,}")
        else:
            skipped_count += 1
            print("⊘ No attendance data")
        
        # Delay to avoid rate limiting
        if i < len(new_games):  # Don't delay after last one
            time.sleep(delay)
    
    # Sort by attendance
    records['games'].sort(key=lambda x: x['attendance'], reverse=True)
    
    # Save
    save_attendance_records(records)
    
    print()
    print("=" * 60)
    print(f"✅ Import complete!")
    print(f"  Imported: {imported_count}")
    print(f"  Skipped: {skipped_count}")
    print(f"  Total records: {len(records['games'])}")
    
    return imported_count


def add_game_attendance(game_analysis_data):
    """
    Add a single game's attendance to the records from game_analysis data
    
    Args:
        game_analysis_data: Dict from game_analysis.py output
    
    Returns:
        Bool - True if added, False if already exists
    """
    
    # Load existing records
    records = load_attendance_records()
    
    # Extract game info
    game_info = game_analysis_data.get('game_info', {})
    game_id = game_info.get('game_id')
    
    # Check if game already exists
    existing_ids = [g['game_id'] for g in records['games']]
    
    if game_id in existing_ids:
        print(f"  ℹ️  Game {game_id} already in attendance records")
        return False
    
    # Parse attendance
    attendance_str = game_info.get('attendance', '0')
    try:
        attendance = int(str(attendance_str).replace(',', ''))
    except:
        attendance = 0
    
    # Skip if no attendance data
    if attendance == 0:
        print(f"  ⚠️  No attendance data for game {game_id}")
        return False
    
    # Create attendance record
    record = {
        'game_id': game_id,
        'date': game_info.get('date'),
        'home_team': game_info.get('home_team'),
        'visitor_team': game_info.get('visitor_team'),
        'venue': game_info.get('venue'),
        'attendance': attendance,
        'final_score': game_info.get('final_score'),
        'winner': game_info.get('winner'),
        'added_at': datetime.now().isoformat()
    }
    
    # Add to records
    records['games'].append(record)
    
    # Sort by attendance (optional - keeps them organized)
    records['games'].sort(key=lambda x: x['attendance'], reverse=True)
    
    # Save
    save_attendance_records(records)
    
    print(f"  ✅ Added game {game_id} (attendance: {attendance:,})")
    
    return True


def update_attendance_from_game_analysis(game_id):
    """
    Load a game analysis JSON and add its attendance
    
    Args:
        game_id: Game ID to process
    
    Returns:
        Bool - success
    """
    
    # Load game analysis JSON
    analysis_file = f"outputs/game_analysis_{game_id}.json"
    
    if not os.path.exists(analysis_file):
        print(f"❌ Game analysis file not found: {analysis_file}")
        return False
    
    with open(analysis_file, 'r') as f:
        analysis_data = json.load(f)
    
    # Add to attendance records
    return add_game_attendance(analysis_data)


def scan_and_update_all_games():
    """
    Scan all game analysis files and add any missing attendance records
    
    Returns:
        Int - number of new games added
    """
    
    print("🔍 Scanning for new games to add to attendance records...")
    
    outputs_dir = "outputs"
    if not os.path.exists(outputs_dir):
        print("❌ No outputs directory found")
        return 0
    
    new_games_added = 0
    
    # Loop through all game analysis files
    for filename in os.listdir(outputs_dir):
        if filename.startswith("game_analysis_") and filename.endswith(".json"):
            # Extract game ID
            game_id = filename.replace("game_analysis_", "").replace(".json", "")
            
            # Try to add it
            if update_attendance_from_game_analysis(game_id):
                new_games_added += 1
    
    print(f"\n✅ Added {new_games_added} new game(s) to attendance records")
    
    return new_games_added


# ============================================================================
# STATISTICS & ANALYSIS
# ============================================================================

def get_attendance_stats():
    """
    Calculate attendance statistics
    
    Returns:
        Dict with stats, or None if no data
    """
    
    records = load_attendance_records()
    games = records['games']
    
    if not games:
        return None
    
    attendances = [g['attendance'] for g in games]
    
    stats = {
        'total_games': len(games),
        'average': sum(attendances) / len(attendances),
        'max': max(attendances),
        'min': min(attendances),
        'total_attendance': sum(attendances),
        'highest_game': max(games, key=lambda x: x['attendance']),
        'lowest_game': min(games, key=lambda x: x['attendance'])
    }
    
    return stats


def get_high_attendance_games(threshold_percentile=80):
    """
    Get games with attendance above a certain percentile
    
    Args:
        threshold_percentile: Percentile threshold (default 80)
    
    Returns:
        List of high-attendance games
    """
    
    records = load_attendance_records()
    games = records['games']
    
    if len(games) < 5:
        print("Not enough games to calculate percentiles")
        return []
    
    # Calculate threshold
    try:
        import numpy as np
        attendances = [g['attendance'] for g in games]
        threshold = np.percentile(attendances, threshold_percentile)
    except ImportError:
        # Fallback if numpy not available
        attendances = sorted([g['attendance'] for g in games])
        index = int(len(attendances) * threshold_percentile / 100)
        threshold = attendances[index]
    
    # Filter games above threshold
    high_att_games = [g for g in games if g['attendance'] >= threshold]
    
    return high_att_games


def get_team_attendance_averages():
    """
    Calculate average home attendance by team
    
    Returns:
        List of dicts with team attendance data
    """
    
    records = load_attendance_records()
    games = records['games']
    
    # Group by home team
    team_totals = {}
    team_counts = {}
    
    for game in games:
        home = game['home_team']
        
        if home not in team_totals:
            team_totals[home] = 0
            team_counts[home] = 0
        
        team_totals[home] += game['attendance']
        team_counts[home] += 1
    
    # Calculate averages
    team_averages = [
        {
            'team': team,
            'avg_attendance': team_totals[team] / team_counts[team],
            'total_attendance': team_totals[team],
            'games': team_counts[team]
        }
        for team in team_totals
    ]
    
    # Sort by average
    team_averages.sort(key=lambda x: x['avg_attendance'], reverse=True)
    
    return team_averages


# ============================================================================
# REPORTING
# ============================================================================

def generate_attendance_report():
    """Generate and display attendance report"""
    
    print("🎫 PWHL ATTENDANCE ANALYSIS")
    print("=" * 60)
    
    stats = get_attendance_stats()
    
    if not stats:
        print("No attendance data available")
        print("\nRun with --import to fetch from API")
        print("   or --scan to import from local game analysis files")
        return
    
    # Overall stats
    print(f"\n📊 Overall Stats ({stats['total_games']} games):")
    print(f"  Total Attendance: {stats['total_attendance']:,}")
    print(f"  Average: {stats['average']:,.0f}")
    print(f"  Highest: {stats['max']:,}")
    print(f"  Lowest: {stats['min']:,}")
    
    # Highest attended game
    print(f"\n🔥 Highest Attended Game:")
    highest = stats['highest_game']
    print(f"  {highest['visitor_team']} @ {highest['home_team']}")
    print(f"  Attendance: {highest['attendance']:,}")
    print(f"  Venue: {highest['venue']}")
    print(f"  Date: {highest['date']}")
    
    # Lowest attended game
    print(f"\n📉 Lowest Attended Game:")
    lowest = stats['lowest_game']
    print(f"  {lowest['visitor_team']} @ {lowest['home_team']}")
    print(f"  Attendance: {lowest['attendance']:,}")
    print(f"  Venue: {lowest['venue']}")
    print(f"  Date: {lowest['date']}")
    
    # Team averages
    print(f"\n🏟️  Average Home Attendance by Team:")
    team_avgs = get_team_attendance_averages()
    
    for team_data in team_avgs:
        print(f"  {team_data['team']}: {team_data['avg_attendance']:,.0f} "
              f"({team_data['games']} games)")
    
    # High attendance games
    print(f"\n⭐ High Attendance Games (Top 20%):")
    high_games = get_high_attendance_games(threshold_percentile=80)
    
    for game in high_games[:10]:  # Show top 10
        print(f"  {game['visitor_team']} @ {game['home_team']}: "
              f"{game['attendance']:,} ({game['date']})")


# ============================================================================
# MAIN & CLI
# ============================================================================

def print_usage():
    """Print usage instructions"""
    print("\nPWHL Attendance Analysis Tool")
    print("=" * 60)
    print("\nUsage:")
    print("  --import          Import last 10 completed games from API (test)")
    print("  --import --full   Import ALL completed games from API (slow!)")
    print("  --scan            Scan local game_analysis files")
    print("  --report          Show attendance report")
    print("  --add <id>        Add specific game from API")
    print()
    print("Examples:")
    print("  python3 attendance_analysis.py --import")
    print("  python3 attendance_analysis.py --import --full")
    print("  python3 attendance_analysis.py --add 235")
    print("  python3 attendance_analysis.py --report")


def main():
    import sys
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == '--import':
            # Import historical data from API
            # Default: import 10 games as test
            max_games = 10
            
            if len(sys.argv) > 2 and sys.argv[2] == '--full':
                max_games = None  # Import all
                print("⚠️  Full import selected - this will take several minutes")
                confirm = input("Continue? (y/n): ")
                if confirm.lower() != 'y':
                    print("Cancelled")
                    return
            
            import_historical_attendance(max_games=max_games)
            
            # Show report after import
            print("\n")
            generate_attendance_report()
        
        elif command == '--scan':
            # Scan local game analysis files (original functionality)
            scan_and_update_all_games()
            generate_attendance_report()
        
        elif command == '--report':
            # Just show the report
            generate_attendance_report()
        
        elif command == '--add':
            # Add specific game
            if len(sys.argv) < 3:
                print("Usage: python3 attendance_analysis.py --add <game_id>")
                return
            
            game_id = sys.argv[2]
            
            # Try to import from API
            print(f"Fetching game {game_id} from API...")
            record = fetch_game_attendance_from_api(game_id)
            
            if record:
                records = load_attendance_records()
                
                # Check if exists
                existing_ids = [g['game_id'] for g in records['games']]
                if game_id in existing_ids:
                    print(f"  ℹ️  Game {game_id} already in records")
                else:
                    records['games'].append(record)
                    records['games'].sort(key=lambda x: x['attendance'], reverse=True)
                    save_attendance_records(records)
                    print(f"  ✅ Added game {game_id} (attendance: {record['attendance']:,})")
            else:
                print(f"  ❌ Could not fetch game {game_id}")
        
        elif command == '--help' or command == '-h':
            print_usage()
        
        else:
            print(f"Unknown command: {command}")
            print_usage()
    
    else:
        # Default: show report
        generate_attendance_report()


if __name__ == "__main__":
    main()