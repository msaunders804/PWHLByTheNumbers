"""
Twitter Client - Handles posting tweets to Twitter
"""

import os
from datetime import datetime

# Try to import tweepy, but make it optional
try:
    import tweepy
    TWEEPY_AVAILABLE = True
except ImportError:
    TWEEPY_AVAILABLE = False
    print("⚠️  tweepy not installed. Run: pip install tweepy")

# Configuration (import from config if available)
try:
    from config import (
        TWITTER_ENABLED,
        TWITTER_API_KEY,
        TWITTER_API_SECRET,
        TWITTER_ACCESS_TOKEN,
        TWITTER_ACCESS_TOKEN_SECRET
    )
except ImportError:
    TWITTER_ENABLED = False
    TWITTER_API_KEY = None
    TWITTER_API_SECRET = None
    TWITTER_ACCESS_TOKEN = None
    TWITTER_ACCESS_TOKEN_SECRET = None


def create_twitter_client():
    """
    Create and authenticate Twitter API client
    
    Returns:
        Tweepy Client object or None
    """
    
    if not TWITTER_ENABLED:
        print("⚠️  Twitter integration is disabled in config.py")
        return None
    
    if not TWEEPY_AVAILABLE:
        print("❌ tweepy library not available")
        return None
    
    if not all([TWITTER_API_KEY, TWITTER_API_SECRET, 
                TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET]):
        print("❌ Twitter API credentials not configured")
        return None
    
    try:
        client = tweepy.Client(
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN,
            access_token_secret=TWITTER_ACCESS_TOKEN_SECRET
        )
        
        # Test authentication
        client.get_me()
        
        return client
        
    except Exception as e:
        print(f"❌ Failed to create Twitter client: {e}")
        return None


def post_tweet(tweet_text, dry_run=True):
    """
    Post a tweet (or simulate posting)
    
    Args:
        tweet_text: The tweet to post
        dry_run: If True, don't actually post (default: True for safety)
    
    Returns:
        Dict with result info
    """
    
    if dry_run:
        print("🔍 DRY RUN - Would post:")
        print(f"   '{tweet_text}'")
        print(f"   Length: {len(tweet_text)} characters")
        return {
            'success': True,
            'dry_run': True,
            'tweet_id': None,
            'message': 'Dry run successful'
        }
    
    # Actual posting
    client = create_twitter_client()
    
    if not client:
        return {
            'success': False,
            'error': 'Twitter client not configured'
        }
    
    try:
        # Post the tweet
        response = client.create_tweet(text=tweet_text)
        
        tweet_id = response.data['id']
        
        print(f"✅ Tweet posted successfully!")
        print(f"   Tweet ID: {tweet_id}")
        print(f"   URL: https://twitter.com/user/status/{tweet_id}")
        
        return {
            'success': True,
            'dry_run': False,
            'tweet_id': tweet_id,
            'message': 'Tweet posted successfully',
            'url': f'https://twitter.com/user/status/{tweet_id}'
        }
        
    except Exception as e:
        print(f"❌ Failed to post tweet: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def save_as_draft(tweet_text, game_id, draft_type='general'):
    """
    Save tweet as a local draft file
    Useful when Twitter API is not configured or for review
    
    Args:
        tweet_text: The tweet content
        game_id: Game ID for reference
        draft_type: Type of tweet (game_summary, hot_player, etc.)
    
    Returns:
        Dict with draft info
    """
    
    import json
    
    # Create drafts directory
    drafts_dir = "twitter_drafts_pending"
    os.makedirs(drafts_dir, exist_ok=True)
    
    # Create draft file
    draft = {
        'tweet': tweet_text,
        'game_id': game_id,
        'type': draft_type,
        'created_at': datetime.now().isoformat(),
        'status': 'pending',
        'posted': False
    }
    
    # Save individual draft
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    draft_file = f"{drafts_dir}/draft_{draft_type}_game_{game_id}_{timestamp}.json"
    
    with open(draft_file, 'w') as f:
        json.dump(draft, f, indent=2)
    
    print(f"💾 Draft saved to: {draft_file}")
    
    return draft


def list_pending_drafts():
    """
    List all pending Twitter drafts
    
    Returns:
        List of draft dicts
    """
    
    import json
    
    drafts_dir = "twitter_drafts_pending"
    
    if not os.path.exists(drafts_dir):
        return []
    
    drafts = []
    
    for filename in os.listdir(drafts_dir):
        if filename.endswith('.json'):
            filepath = os.path.join(drafts_dir, filename)
            
            try:
                with open(filepath, 'r') as f:
                    draft = json.load(f)
                    draft['filename'] = filename
                    draft['filepath'] = filepath
                    drafts.append(draft)
            except:
                continue
    
    # Sort by creation time (newest first)
    drafts.sort(key=lambda x: x['created_at'], reverse=True)
    
    return drafts


def review_and_post_drafts():
    """
    Interactive CLI to review and post pending drafts
    """
    
    import json
    
    drafts = list_pending_drafts()
    
    if not drafts:
        print("📭 No pending drafts found")
        return
    
    print("📋 TWITTER DRAFTS REVIEW")
    print("=" * 60)
    
    for i, draft in enumerate(drafts, 1):
        if draft.get('posted'):
            continue
        
        print(f"\n--- DRAFT #{i} ---")
        print(f"Type: {draft.get('type', 'unknown')}")
        print(f"Game: #{draft.get('game_id', 'unknown')}")
        print(f"Created: {draft.get('created_at', 'unknown')}")
        print(f"\nTweet:\n{draft['tweet']}")
        print(f"\nLength: {len(draft['tweet'])} characters")
        
        # Ask user what to do
        choice = input("\n[P]ost / [S]kip / [D]elete / [Q]uit? ").lower()
        
        if choice == 'p':
            # Post the tweet
            result = post_tweet(draft['tweet'], dry_run=False)
            
            if result['success']:
                print("✅ Posted successfully!")
                
                # Mark as posted
                draft['posted'] = True
                draft['posted_at'] = datetime.now().isoformat()
                draft['tweet_id'] = result.get('tweet_id')
                
                # Update file
                with open(draft['filepath'], 'w') as f:
                    json.dump(draft, f, indent=2)
            else:
                print(f"❌ Error: {result.get('error')}")
        
        elif choice == 'd':
            # Delete draft
            os.remove(draft['filepath'])
            print("🗑️  Draft deleted")
        
        elif choice == 'q':
            print("Exiting...")
            break
        
        else:
            print("⏭️  Skipped")


if __name__ == "__main__":
    # If run directly, launch review interface
    review_and_post_drafts()