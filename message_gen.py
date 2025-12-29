"""
Main Tweet Generator
Analyzes a game and generates tweet drafts
"""

import json
import os
from datetime import datetime
from ai_client import call_ai, validate_tweet
from prompts import (
    build_game_summary_prompt,
    build_hot_player_prompt,
    build_goalie_spotlight_prompt
)
from config import SAVE_DRAFTS, DRAFTS_FOLDER

def load_game_analysis(game_id):
    """
    Load analysis from game_analysis.py output
    
    Args:
        game_id: Game ID number
    
    Returns:
        Dict with parsed analysis data
    """
    
    # TODO #14: Load the analysis file
    # The game_analysis.py script saves to outputs/game_analysis_{id}.txt
    # But we need the JSON data, not the text summary
    # Hint: You might need to modify game_analysis.py to also save JSON
    
    filepath = f"outputs/game_analysis_{game_id}.json"
    
    # Check if file exists
    if not os.path.exists(filepath):  # How do you check if a file exists?
        raise FileNotFoundError(f"Analysis file not found: {filepath}")
    
    # Load and parse JSON
    with open(filepath, 'r') as f:
        data = json.load(f)  # How do you load JSON?
    
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
    
    # TODO #15: Generate game summary tweet
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
    
    # TODO #16: Generate hot player tweet (if we have hot players)
    if hot_players and len(hot_players) > 0:
        print("Generating hot player tweet...")
        
        # Get the top player
        top_player = hot_players[0]  # How do you get the first player from the list?
        
        # Build prompt
        player_prompt = build_hot_player_prompt(top_player, game_info)  # What args?
        
        # Generate
        player_tweet = call_ai(player_prompt)  # Call the AI

        # Validate
        is_valid, issues = validate_tweet(player_tweet)  # Validate the tweet
        
        # Add to drafts
        drafts.append({
            'type': 'hot_player',
            'player': top_player['name'],
            'tweet': player_tweet,  
            'valid': is_valid, 
            'issues': issues, 
            'timestamp': datetime.now().isoformat()
        })
    
    # TODO #17: Generate goalie spotlight tweet (if we have hot goalies)
    if hot_goalies and len(hot_goalies) > 0:  # What's the condition?
        print("Generating goalie spotlight tweet...")
        
        # You write the rest following the pattern above!
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
    
    return drafts


def save_drafts(drafts, game_id):
    """
    Save tweet drafts to file
    
    Args:
        drafts: List of tweet dicts
        game_id: Game ID for filename
    """
    
    # TODO #18: Create output directory if needed
    os.makedirs(DRAFTS_FOLDER, exist_ok=True)  
    
    # TODO #19: Save as JSON
    filename = f"{DRAFTS_FOLDER}/game_{game_id}_tweets.json"
    
    with open(filename, 'w') as f:
        json.dump(drafts, f, indent=2) 
    
    print(f"\n💾 Drafts saved to: {filename}")
    
    # TODO #20: Also save as readable text
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
    
    # TODO #21: Get game ID from command line argument
    if len(sys.argv) < 2:
        print("Usage: python tweet_generator.py <game_id>")
        print("Example: python tweet_generator.py 235")
        return
    
    game_id = sys.argv[1]
    
    print(f"\n🎯 Generating tweets for Game #{game_id}")
    
    # Load analysis
    print("\n📊 Loading game analysis...")
    try:
        analysis = load_game_analysis(game_id)
    except FileNotFoundError as e:
        print(f"❌ {e}")
        print("\n💡 Make sure you've run: python game_analysis.py {game_id}")
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