"""
Main Tweet Generator
Analyzes a game and generates tweet drafts
"""

import json
import os
import glob
from datetime import datetime
from ai_client import call_ai, validate_tweet
from prompts import (
    build_game_summary_prompt,
    build_hot_player_prompt,
    build_goalie_spotlight_prompt,
    build_attendance_highlight_prompt
)
from config import SAVE_DRAFTS, DRAFTS_FOLDER

def find_most_recent_game_analysis():
    """
    Find the most recently created game analysis file
    
    Returns:
        Tuple of (game_id, filepath) or (None, None) if not found
    """
    
    # Get all game analysis JSON files
    analysis_files = glob.glob("outputs/game_analysis_*.json")
    
    if not analysis_files:
        return None, None
    
    # Sort by modification time (most recent first)
    analysis_files.sort(key=os.path.getmtime, reverse=True)
    
    # Get the most recent file
    most_recent = analysis_files[0]
    
    # Extract game ID from filename
    # Format: outputs/game_analysis_235.json
    filename = os.path.basename(most_recent)
    game_id = filename.replace("game_analysis_", "").replace(".json", "")
    
    return game_id, most_recent


def load_game_analysis(game_id):
    """
    Load analysis from game_analysis.py output
    
    Args:
        game_id: Game ID number
    
    Returns:
        Dict with parsed analysis data
    """
    
    filepath = f"outputs/game_analysis_{game_id}.json"
    
    # Check if file exists
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Analysis file not found: {filepath}")
    
    # Load and parse JSON
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    return data


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
    
    # Generate game summary tweet
    print("Generating game summary tweet...")
    summary_prompt = build_game_summary_prompt(game_info, hot_players, hot_goalies)  
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
    
    # Generate hot player tweet (if we have hot players)
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
    
    # Check if attendance is noteworthy
    attendance = game_info.get('attendance', 'N/A')
    
    # Convert to int for comparison
    try:
        attendance_num = int(str(attendance).replace(',', ''))
    except:
        attendance_num = 0
    
    # If attendance is over 7,000, generate special tweet
    HIGH_ATTENDANCE_THRESHOLD = 7000  # Adjust based on your data
    
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
    
    print(f"\n💾 Drafts saved to: {filename}")
    
    # Also save as readable text
    text_filename = f"{DRAFTS_FOLDER}/game_{game_id}_tweets.txt"
    
    with open(text_filename, 'w') as f:
        f.write(f"Tweet Drafts for Game #{game_id}\n")
        f.write("=" * 60 + "\n\n")
        
        for i, draft in enumerate(drafts, 1):
            f.write(f"DRAFT #{i} - {draft['type'].upper()}\n")
            f.write("-" * 60 + "\n")
            f.write(f"{draft['tweet']}\n\n")
            
            if draft['valid']:
                f.write("✅ Valid\n")
            else:
                f.write(f"❌ Issues: {', '.join(draft['issues'])}\n")
            
            f.write(f"Length: {len(draft['tweet'])} characters\n")
            f.write("\n" + "=" * 60 + "\n\n")
    
    print(f"💾 Text version saved to: {text_filename}")


def main():
    """Main function"""
    import sys
    
    print("🤖 AI Tweet Draft Generator")
    print("=" * 60)
    
    # Check for game ID argument
    if len(sys.argv) < 2:
        # AUTO MODE - Find most recent game analysis
        print("\n🔍 AUTO MODE - Finding most recent game analysis...")
        game_id, filepath = find_most_recent_game_analysis()
        
        if not game_id:
            print("❌ No game analysis files found in outputs/")
            print("\n💡 Run one of these first:")
            print("   python3 game_analysis.py              (auto-analyze latest game)")
            print("   python3 game_analysis.py <game_id>    (analyze specific game)")
            return
        
        print(f"✓ Found most recent: Game #{game_id}")
        print(f"  File: {filepath}")
    else:
        # MANUAL MODE - Use provided game ID
        game_id = sys.argv[1]
        print(f"\n🎯 MANUAL MODE - Generating tweets for Game #{game_id}")
    
    # Load analysis
    print("\n📊 Loading game analysis...")
    try:
        analysis = load_game_analysis(game_id)
        
        # Show game details
        game_info = analysis['game_info']
        print(f"✓ Loaded game data:")
        print(f"  {game_info['visitor_team']} @ {game_info['home_team']}")
        print(f"  Final: {game_info['final_score']}")
        print(f"  Date: {game_info['date']}")
        
    except FileNotFoundError as e:
        print(f"❌ {e}")
        print(f"\n💡 Make sure you've run: python3 game_analysis.py")
        return
    
    # Generate tweets
    print("\n✍️ Generating tweet drafts...")
    drafts = generate_tweet_drafts(analysis)
    
    # Display results
    print(f"\n📝 Generated {len(drafts)} tweet draft(s):")
    for i, draft in enumerate(drafts, 1):
        print(f"\n--- DRAFT #{i} ({draft['type']}) ---")
        print(draft['tweet'])
        if not draft['valid']:
            print(f"⚠️  Issues: {', '.join(draft['issues'])}")
    
    # Save
    if SAVE_DRAFTS:
        save_drafts(drafts, game_id)
    
    print("\n✅ Complete!")


if __name__ == "__main__":
    main()