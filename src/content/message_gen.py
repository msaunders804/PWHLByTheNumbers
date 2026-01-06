"""
Main Tweet Generator
Analyzes a game and generates tweet drafts using database
"""

import json
import os
import sys
import glob
from datetime import datetime

# Add project root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from src.clients.ai_client import call_ai, validate_tweet
from src.content.prompts import (
    build_game_summary_prompt,
    build_hot_player_prompt,
    build_goalie_spotlight_prompt,
    build_attendance_highlight_prompt
)
from config import SAVE_DRAFTS, DRAFTS_FOLDER
from src.database.db_queries import get_most_recent_completed_game, get_game_analysis, ensure_game_in_db

def find_most_recent_game_from_db():
    """
    Find the most recently completed game from the database

    Returns:
        Tuple of (game_id, game_info_dict) or (None, None) if not found
    """
    try:
        game_info = get_most_recent_completed_game()

        if not game_info:
            return None, None

        return game_info['game_id'], game_info

    except Exception as e:
        print(f"  ❌ Error querying database: {e}")
        return None, None


def load_game_analysis(game_id):
    """
    Load analysis from database

    Args:
        game_id: Game ID number

    Returns:
        Dict with parsed analysis data
    """
    try:
        # Ensure game is in database
        ensure_game_in_db(game_id)

        # Get analysis from database
        analysis = get_game_analysis(game_id)

        if not analysis:
            raise ValueError(f"Could not analyze game {game_id}")

        return analysis

    except Exception as e:
        raise FileNotFoundError(f"Error loading game {game_id} from database: {e}")


def generate_tweet_drafts(analysis_data):
    """
    Generate multiple tweet options from game analysis
    
    Args:
        analysis_data: Dict from game_analysis.py
    
    Returns:
        List of tweet dicts with metadata
    """
    
    drafts = []

    # Extract data
    game_info = analysis_data['game_info']
    hot_players = analysis_data['hot_players']
    hot_goalies = analysis_data['hot_goalies']
    firsts = analysis_data.get('firsts', None)

    # Generate game summary tweet
    print("Generating game summary tweet...")
    summary_prompt = build_game_summary_prompt(game_info, hot_players, hot_goalies, firsts)
    summary_tweet = call_ai(summary_prompt) 

    # Validate
    is_valid, issues = validate_tweet(summary_tweet)
    
    drafts.append({
        'type': 'game_summary',
        'tweet': summary_tweet,
        'valid': is_valid,
        'issues': issues,
        'timestamp': datetime.now().isoformat()
    })
    
    ''' # Generate hot player tweet (if we have hot players)
    if hot_players and len(hot_players) > 0:
        print("Generating hot player tweet...")
        
        # Get the top player
        top_player = hot_players[0]
        
        # Build prompt
        player_prompt = build_hot_player_prompt(top_player, game_info)
        
        # Generate
        player_tweet = call_ai(player_prompt)

        # Validate
        is_valid, issues = validate_tweet(player_tweet)
        
        # Add to drafts
        drafts.append({
            'type': 'hot_player',
            'player': top_player['name'],
            'tweet': player_tweet,  
            'valid': is_valid, 
            'issues': issues, 
            'timestamp': datetime.now().isoformat()
        })
    
    # Generate goalie spotlight tweet (if we have hot goalies)
    if hot_goalies and len(hot_goalies) > 0:
        print("Generating goalie spotlight tweet...")
        
        top_goalie = hot_goalies[0]
        goalie_prompt = build_goalie_spotlight_prompt(top_goalie, game_info)
        goalie_tweet = call_ai(goalie_prompt)
        is_valid, issues = validate_tweet(goalie_tweet)

        drafts.append({
            'type': 'goalie_spotlight',
            'goalie': top_goalie['name'],
            'tweet': goalie_tweet,
            'valid': is_valid,
            'issues': issues,
            'timestamp': datetime.now().isoformat()
        })
    '''
    # Check if attendance is noteworthy
    attendance = game_info.get('attendance', 'N/A')
    
    # Convert to int for comparison
    try:
        attendance_num = int(str(attendance).replace(',', ''))
    except:
        attendance_num = 0
    
    # If attendance is over 7,000, generate special tweet

    HIGH_ATTENDANCE_THRESHOLD = 10000  # Adjust based on your data
    
    if attendance_num >= HIGH_ATTENDANCE_THRESHOLD:
        print("Generating high attendance tweet...")
        
        attendance_prompt = build_attendance_highlight_prompt(game_info)
        attendance_tweet = call_ai(attendance_prompt)
        is_valid, issues = validate_tweet(attendance_tweet)
        
        drafts.append({
            'type': 'high_attendance',
            'attendance': attendance_num,
            'tweet': attendance_tweet,
            'valid': is_valid,
            'issues': issues,
            'timestamp': datetime.now().isoformat()
        })
    
    return drafts


def save_drafts(drafts, game_id):
    """
    Save tweet drafts to file
    
    Args:
        drafts: List of tweet dicts
        game_id: Game ID for filename
    """
    
    # Create output directory if needed
    os.makedirs(DRAFTS_FOLDER, exist_ok=True)
    
    # Save as JSON
    filename = f"{DRAFTS_FOLDER}/game_{game_id}_tweets.json"
    
    with open(filename, 'w') as f:
        json.dump(drafts, f, indent=2)
    
    print(f"\n[SAVE] Drafts saved to: {filename}")

    # Also save as readable text
    text_filename = f"{DRAFTS_FOLDER}/game_{game_id}_tweets.txt"

    with open(text_filename, 'w', encoding='utf-8') as f:
        f.write(f"Tweet Drafts for Game #{game_id}\n")
        f.write("=" * 60 + "\n\n")

        for i, draft in enumerate(drafts, 1):
            f.write(f"DRAFT #{i} - {draft['type'].upper()}\n")
            f.write("-" * 60 + "\n")
            f.write(f"{draft['tweet']}\n\n")

            if draft['valid']:
                f.write("[OK] Valid\n")
            else:
                f.write(f"[WARN] Issues: {', '.join(draft['issues'])}\n")

            f.write(f"Length: {len(draft['tweet'])} characters\n")
            f.write("\n" + "=" * 60 + "\n\n")

    print(f"[SAVE] Text version saved to: {text_filename}")


def main():
    """Main function"""
    import sys

    # Set UTF-8 encoding for Windows console
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    print("[AI] Tweet Draft Generator (Database Mode)")
    print("=" * 60)

    # Check for game ID argument
    if len(sys.argv) < 2:
        # AUTO MODE - Find most recent game from database
        print("\n[AUTO] Finding most recent completed game from database...")
        game_id, game_info = find_most_recent_game_from_db()

        if not game_id:
            print("[ERROR] No recent completed games found in database")
            print("\n[INFO] Make sure the database is populated with game data")
            return

        print(f"[OK] Found most recent game: Game #{game_id}")
        print(f"  {game_info['away_team']} @ {game_info['home_team']}")
        print(f"  Final: {game_info['away_score']}-{game_info['home_score']}")
        print(f"  Date: {game_info['date']}")
    else:
        # MANUAL MODE - Use provided game ID
        game_id = sys.argv[1]
        print(f"\n[MANUAL] Generating tweets for Game #{game_id}")

    # Load analysis from database
    print("\n[LOAD] Loading game analysis from database...")
    try:
        analysis = load_game_analysis(game_id)

        # Show game details
        game_info = analysis['game_info']
        print(f"[OK] Loaded game data:")
        print(f"  {game_info['visitor_team']} @ {game_info['home_team']}")
        print(f"  Final: {game_info['final_score']}")
        print(f"  Date: {game_info['date']}")

    except (FileNotFoundError, ValueError) as e:
        print(f"[ERROR] {e}")
        print(f"\n[INFO] Make sure game {game_id} is in the database")
        return

    # Generate tweets
    print("\n[GEN] Generating tweet drafts...")
    drafts = generate_tweet_drafts(analysis)

    # Display results
    print(f"\n[RESULTS] Generated {len(drafts)} tweet draft(s):")
    for i, draft in enumerate(drafts, 1):
        print(f"\n--- DRAFT #{i} ({draft['type']}) ---")
        print(draft['tweet'])
        if not draft['valid']:
            print(f"[WARN] Issues: {', '.join(draft['issues'])}")

    # Save
    if SAVE_DRAFTS:
        save_drafts(drafts, game_id)

    print("\n[OK] Complete!")


if __name__ == "__main__":
    main()