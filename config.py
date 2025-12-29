"""
Configuration for AI Tweet Generator
Stores API keys and settings
"""

AI_PROVIDER = "anthropic"  # Fill this in

# API Keys - Get these from:
# Anthropic: https://console.anthropic.com/
ANTHROPIC_API_KEY = "Enterkey here"  # Your Claude API key here

# AI Model Selection
CLAUDE_MODEL = "claude-sonnet-4-20250514"  # Latest Claude model

# Tweet Settings
MAX_TWEET_LENGTH = 280
INCLUDE_HASHTAGS = True
BRAND_HASHTAGS = ["#PWHL"]  # Add more if you want
TWITTER_ENABLED = True
TWITTER_API_KEY = "Enterkey here"
TWITTER_API_SECRET = "Enterkey here"
TWITTER_ACCESS_TOKEN = "Enterkey here-Enterkey here"
TWITTER_ACCESS_TOKEN_SECRET = "Enterkey here"

# Content Settings
EMOJI_STYLE = "moderate"  # Options: "none", "minimal", "moderate", "heavy"
TONE = "professional, scientific"  # Options: "professional", "exciting", "casual", "dramatic"

# Output Settings
SAVE_DRAFTS = True

DRAFTS_FOLDER = "tweet_drafts"
