#!/usr/bin/env python3
"""
PWHL Analytics Pipeline - Fully Automated
Runs the complete workflow: data update → analysis → tweets → posting
"""

import os
import sys
import json
import subprocess
from datetime import datetime
import time

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
    
    def step1_update_data(self):
        """Step 1: Update all data from API"""
        self.log("\n" + "="*60, "update_data")
        self.log("📡 STEP 1: UPDATING DATA FROM API", "update_data")
        self.log("="*60, "update_data")
        # Check if PowerShell script exists AND we're on Windows (not WSL)
        is_wsl = 'microsoft' in os.uname().release.lower() if hasattr(os, 'uname') else False
        script_path = os.path.join('data processing', 'data_extract.ps1')

        if os.path.exists(script_path) and not is_wsl and os.name == 'nt':
            self.log("Running PowerShell data extraction script...")
            success, output = self.run_command(
                f'powershell -ExecutionPolicy Bypass -File "{script_path}"',
                "Data extraction (PowerShell)"
            )
        else:
            # Use Python fallback (works on Linux/WSL/Mac)
            if is_wsl:
                self.log("WSL detected - using Python fallback for data update...")
            else:
                self.log("PowerShell not available - using Python fallback...")
            
            success = self._update_schedule_python()
        
        return success
    
    def _update_schedule_python(self):
        """Fallback: Update schedule using Python"""
        try:
            import requests
            
            url = "https://lscluster.hockeytech.com/feed/"
            params = {
                'feed': 'modulekit',
                'view': 'scorebar',
                'key': '446521baf8c38984',
                'fmt': 'json',
                'client_code': 'pwhl',
                'lang': 'en',
                'league_id': '1',
                'season_id': '8',
                'numberofdaysahead': '365',
                'numberofdaysback': '365'
            }
            
            self.log("  Downloading schedule from API...")
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            # Remove JavaScript wrapper
            text = response.text
            if text.startswith('angular.callbacks'):
                text = text[text.find('(')+1:text.rfind(')')]
            
            data = json.loads(text)
            
            # Save to file
            os.makedirs('raw_data', exist_ok=True)
            with open('raw_data/schedule.json', 'w') as f:
                json.dump(data, f, indent=2)
            
            self.log("  ✅ Schedule updated successfully")
            return True
            
        except Exception as e:
            self.log(f"  ❌ Failed to update schedule: {e}")
            self.results['errors'].append(f"Schedule update failed: {e}")
            return False
    
    def step2_analyze_games(self):
        """Step 2: Run game analysis on most recent game"""
        self.log("\n" + "="*60, "analyze_games")
        self.log("🔍 STEP 2: ANALYZING RECENT GAMES", "analyze_games")
        self.log("="*60, "analyze_games")
        
        # Use 'python' on Windows, 'python3' on Linux/Mac
        python_cmd = 'python' if os.name == 'nt' else 'python3'
        
        success, output = self.run_command(
            f'{python_cmd} "data processing/game_analysis.py"',
            "Game analysis"
        )
        
        if success:
            # Extract game ID from output (simple parsing)
            try:
                lines = output.split('\n')
                for line in lines:
                    if 'Most Recent: Game #' in line:
                        game_id = line.split('Game #')[1].split()[0]
                        self.results['games_analyzed'].append(game_id)
                        self.log(f"  ✅ Analyzed Game #{game_id}")
                        break
            except:
                pass
        
        return success
    
    def step3_generate_tweets(self):
        """Step 3: Generate tweet drafts"""
        self.log("\n" + "="*60, "generate_tweets")
        self.log("✍️  STEP 3: GENERATING TWEET DRAFTS", "generate_tweets")
        self.log("="*60, "generate_tweets")
        
        success, output = self.run_command(
            'python3 message_gen.py',
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
        self.log("🚀 PWHL ANALYTICS PIPELINE - STARTING")
        self.log("🚀"*30)
        self.log(f"\nMode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        self.log(f"Auto-post: {'ENABLED' if AUTO_POST_VALID_TWEETS else 'DISABLED'}")
        self.log(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Step 1: Update data
        if not self.step1_update_data():
            self.log("\n❌ Pipeline failed at Step 1 (Data Update)")
            self.save_results()
            return False
        
        # Step 2: Analyze games
        if not self.step2_analyze_games():
            self.log("\n❌ Pipeline failed at Step 2 (Game Analysis)")
            self.save_results()
            return False
        
        # Step 3: Generate tweets
        success, drafts = self.step3_generate_tweets()
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