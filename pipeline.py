#!/usr/bin/env python3
"""
PWHL Analytics Pipeline - Streamlined with Database
Runs the complete workflow: check recent game → fetch if needed → generate tweets → post
"""

import os
import sys
import json
import subprocess
from datetime import datetime
import time
from db_queries import get_most_recent_completed_game, ensure_game_in_db, get_game_analysis

# Configuration
DRY_RUN = True  # Set to False to actually post to Twitter
AUTO_POST_VALID_TWEETS = True  # Auto-post tweets with no issues
REQUIRE_ATTENDANCE_THRESHOLD = 7000  # Only post attendance tweets above this

class PWHLPipeline:
    def __init__(self, dry_run=True):
        self.dry_run = dry_run
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'steps': [],
            'games_analyzed': [],
            'tweets_generated': [],
            'tweets_posted': [],
            'errors': []
        }
    
    def log(self, message, step=None):
        """Log a message and optionally add to results"""
        print(message)
        if step:
            self.results['steps'].append({
                'step': step,
                'message': message,
                'timestamp': datetime.now().isoformat()
            })
    
    def run_command(self, command, description):
        """Run a shell command and capture output"""
        self.log(f"\n{'='*60}")
        self.log(f"🔧 {description}")
        self.log(f"{'='*60}")
        
        try:
            # Run command and stream output in real-time
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            # Collect output
            stdout_lines = []
            stderr_lines = []
            
            # Read output line by line
            for line in process.stdout:
                print(line, end='')  # Show in real-time
                stdout_lines.append(line)
            
            # Wait for completion
            process.wait(timeout=300)
            
            # Get any stderr
            stderr = process.stderr.read()
            if stderr:
                stderr_lines.append(stderr)
                print(stderr, end='')
            
            stdout = ''.join(stdout_lines)
            stderr = ''.join(stderr_lines)
            
            if process.returncode == 0:
                self.log(f"✅ {description} - Success")
                return True, stdout
            else:
                error_msg = f"❌ {description} - Failed"
                if stderr:
                    error_msg += f": {stderr}"
                self.log(error_msg)
                self.results['errors'].append(error_msg)
                return False, stderr
                
        except subprocess.TimeoutExpired:
            error_msg = f"⏱️  {description} - Timeout"
            self.log(error_msg)
            self.results['errors'].append(error_msg)
            return False, "Timeout"
        except Exception as e:
            error_msg = f"💥 {description} - Error: {e}"
            self.log(error_msg)
            self.results['errors'].append(error_msg)
            return False, str(e)
    
    def step1_get_recent_game(self):
        """Step 1: Get most recent game from database"""
        self.log("\n" + "="*60, "get_recent_game")
        self.log("🔍 STEP 1: FINDING MOST RECENT GAME", "get_recent_game")
        self.log("="*60, "get_recent_game")

        try:
            self.log("  Querying database for most recent completed game...")
            game_info = get_most_recent_completed_game()

            if not game_info:
                self.log("  ❌ No completed games found in database")
                self.results['errors'].append("No completed games in database")
                return False, None

            self.log(f"  ✅ Found: Game #{game_info['game_id']}")
            self.log(f"     {game_info['away_team']} @ {game_info['home_team']}")
            self.log(f"     Final: {game_info['away_score']}-{game_info['home_score']}")
            self.log(f"     Date: {game_info['date']}")

            self.results['games_analyzed'].append(str(game_info['game_id']))
            return True, game_info

        except Exception as e:
            error_msg = f"Error querying database: {e}"
            self.log(f"  ❌ {error_msg}")
            self.results['errors'].append(error_msg)
            return False, None
    
    def step2_ensure_game_data(self, game_id):
        """Step 2: Ensure game data is in database (fetch from API if needed)"""
        self.log("\n" + "="*60, "ensure_game_data")
        self.log("📥 STEP 2: ENSURING GAME DATA IN DATABASE", "ensure_game_data")
        self.log("="*60, "ensure_game_data")

        try:
            success = ensure_game_in_db(game_id)

            if success:
                self.log(f"  ✅ Game {game_id} data ready in database")
                return True
            else:
                error_msg = f"Failed to ensure game {game_id} in database"
                self.log(f"  ❌ {error_msg}")
                self.results['errors'].append(error_msg)
                return False

        except Exception as e:
            error_msg = f"Error ensuring game data: {e}"
            self.log(f"  ❌ {error_msg}")
            self.results['errors'].append(error_msg)
            return False
    
    def step3_generate_tweets(self, game_id):
        """Step 3: Generate tweet drafts"""
        self.log("\n" + "="*60, "generate_tweets")
        self.log("✍️  STEP 3: GENERATING TWEET DRAFTS", "generate_tweets")
        self.log("="*60, "generate_tweets")

        # Use 'python' on Windows, 'python3' on Linux/Mac
        python_cmd = 'python' if os.name == 'nt' else 'python3'

        success, output = self.run_command(
            f'{python_cmd} message_gen.py {game_id}',
            "Tweet generation"
        )

        if success:
            # Find the tweet drafts file
            try:
                import glob
                draft_files = glob.glob('tweet_drafts/game_*_tweets.json')
                if draft_files:
                    # Get most recent
                    draft_files.sort(key=os.path.getmtime, reverse=True)
                    latest_draft = draft_files[0]

                    with open(latest_draft, 'r') as f:
                        drafts = json.load(f)

                    self.log(f"  ✅ Generated {len(drafts)} tweet draft(s)")
                    self.results['tweets_generated'] = drafts

                    return True, drafts
            except Exception as e:
                self.log(f"  ⚠️  Could not load draft files: {e}")

        return success, []
    
    def step4_post_to_twitter(self, drafts):
        """Step 4: Post tweets to Twitter (with human-in-the-loop option)"""
        self.log("\n" + "="*60, "post_tweets")
        self.log("🐦 STEP 4: POSTING TO TWITTER", "post_tweets")
        self.log("="*60, "post_tweets")
        
        if not drafts:
            self.log("  ⚠️  No drafts to post")
            return True
        
        # Try to send email notification first
        try:
            from email_notifications import send_tweet_drafts_email
            
            # Extract game info from first draft's context
            game_info = None
            try:
                # Get game ID from results
                if self.results['games_analyzed']:
                    game_id = self.results['games_analyzed'][0]
                    
                    # Load game analysis to get details
                    import json
                    with open(f'outputs/game_analysis_{game_id}.json', 'r') as f:
                        analysis = json.load(f)
                        game_info = analysis.get('game_info', {})
            except:
                pass
            
            # Send email
            self.log("\n📧 Sending email notification with tweet drafts...")
            email_sent = send_tweet_drafts_email(drafts, game_info)
            
            if email_sent:
                self.log("  ✅ Email sent successfully!")
            else:
                self.log("  ⚠️  Email not sent (check configuration)")
                
        except ImportError:
            self.log("  ⚠️  Email notifications not available")
        except Exception as e:
            self.log(f"  ⚠️  Email error: {e}")
        
        # If dry run, just show what would be posted
        if self.dry_run:
            self.log("\n  🔍 DRY RUN MODE - Not actually posting")
            for i, draft in enumerate(drafts, 1):
                self.log(f"\n  Would post draft #{i} ({draft['type']}):")
                self.log(f"  {draft['tweet']}")
                if not draft['valid']:
                    self.log(f"  ⚠️  Issues: {', '.join(draft['issues'])}")
            return True
        
        # Import Twitter client
        try:
            from twitter_client import post_tweet
        except ImportError:
            self.log("  ❌ Twitter client not available")
            self.log("  💡 Tweets saved in email - post manually")
            return True  # Not a failure if email was sent
        
        # Post each valid draft
        for i, draft in enumerate(drafts, 1):
            tweet_text = draft['tweet']
            tweet_type = draft['type']
            
            # Skip if not valid
            if not draft['valid']:
                self.log(f"  ⏭️  Skipping draft #{i} ({tweet_type}) - validation issues")
                continue
            
            # Skip attendance if below threshold
            if tweet_type == 'high_attendance':
                attendance = draft.get('attendance', 0)
                if attendance < REQUIRE_ATTENDANCE_THRESHOLD:
                    self.log(f"  ⏭️  Skipping attendance tweet - below threshold")
                    continue
            
            # Post tweet
            if AUTO_POST_VALID_TWEETS:
                self.log(f"\n  📤 Posting draft #{i} ({tweet_type})...")
                self.log(f"  Tweet: {tweet_text}")
                
                result = post_tweet(tweet_text, dry_run=False)
                
                if result['success']:
                    self.log(f"  ✅ Posted successfully!")
                    self.results['tweets_posted'].append({
                        'type': tweet_type,
                        'tweet': tweet_text,
                        'tweet_id': result.get('tweet_id'),
                        'timestamp': datetime.now().isoformat()
                    })
                else:
                    error_msg = f"Failed to post {tweet_type}: {result.get('error')}"
                    self.log(f"  ❌ {error_msg}")
                    self.results['errors'].append(error_msg)
                
                # Wait between tweets
                if i < len(drafts):
                    self.log("  ⏸️  Waiting 30 seconds before next tweet...")
                    time.sleep(30)
            else:
                self.log(f"  💾 Saving draft #{i} ({tweet_type}) for manual review")
        
        return True
    
    def save_results(self):
        """Save pipeline results to file"""
        output_dir = 'pipeline_logs'
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{output_dir}/pipeline_run_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        self.log(f"\n📊 Pipeline results saved to: {filename}")
        return filename
    
    def run(self):
        """Run the complete pipeline"""
        self.log("\n" + "🚀"*30)
        self.log("🚀 PWHL ANALYTICS PIPELINE - STARTING (DATABASE MODE)")
        self.log("🚀"*30)
        self.log(f"\nMode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        self.log(f"Auto-post: {'ENABLED' if AUTO_POST_VALID_TWEETS else 'DISABLED'}")
        self.log(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        # Step 1: Get most recent game from database
        success, game_info = self.step1_get_recent_game()
        if not success:
            self.log("\n❌ Pipeline failed at Step 1 (Get Recent Game)")
            self.save_results()
            return False

        game_id = game_info['game_id']

        # Step 2: Ensure game data is in database
        if not self.step2_ensure_game_data(game_id):
            self.log("\n❌ Pipeline failed at Step 2 (Ensure Game Data)")
            self.save_results()
            return False

        # Step 3: Generate tweets
        success, drafts = self.step3_generate_tweets(game_id)
        if not success:
            self.log("\n❌ Pipeline failed at Step 3 (Tweet Generation)")
            self.save_results()
            return False

        # Step 4: Post to Twitter
        if not self.step4_post_to_twitter(drafts):
            self.log("\n❌ Pipeline failed at Step 4 (Twitter Posting)")
            self.save_results()
            return False

        # Success!
        self.log("\n" + "✅"*30)
        self.log("✅ PIPELINE COMPLETED SUCCESSFULLY")
        self.log("✅"*30)

        # Summary
        self.log("\n📊 SUMMARY:")
        self.log(f"  Games analyzed: {len(self.results['games_analyzed'])}")
        self.log(f"  Tweets generated: {len(self.results['tweets_generated'])}")
        self.log(f"  Tweets posted: {len(self.results['tweets_posted'])}")
        self.log(f"  Errors: {len(self.results['errors'])}")

        # Save results
        self.save_results()

        return True


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='PWHL Analytics Pipeline')
    parser.add_argument('--live', action='store_true', 
                       help='Run in LIVE mode (actually post to Twitter)')
    parser.add_argument('--no-auto-post', action='store_true',
                       help='Generate tweets but dont auto-post (save for review)')
    
    args = parser.parse_args()
    
    # Set globals based on arguments
    global DRY_RUN, AUTO_POST_VALID_TWEETS
    DRY_RUN = not args.live
    if args.no_auto_post:
        AUTO_POST_VALID_TWEETS = False
    
    # Run pipeline
    pipeline = PWHLPipeline(dry_run=DRY_RUN)
    success = pipeline.run()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()