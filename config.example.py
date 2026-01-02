"""
Configuration Template for PWHL Analytics
Copy this file to config.py and fill in your actual API keys
"""

# AI Provider
AI_PROVIDER = "anthropic"

# API Keys - Get these from:
# Anthropic: https://console.anthropic.com/
ANTHROPIC_API_KEY = "your-claude-api-key-here"

# AI Model Selection
CLAUDE_MODEL = "claude-sonnet-4-20250514"

# Tweet Settings
MAX_TWEET_LENGTH = 280
INCLUDE_HASHTAGS = True
BRAND_HASHTAGS = ["#PWHL"]
TWITTER_ENABLED = True

# Twitter API Keys - Get these from: https://developer.twitter.com/
TWITTER_API_KEY = "your-twitter-api-key-here"
TWITTER_API_SECRET = "your-twitter-api-secret-here"
TWITTER_ACCESS_TOKEN = "your-twitter-access-token-here"
TWITTER_ACCESS_TOKEN_SECRET = "your-twitter-access-token-secret-here"

# Content Settings
EMOJI_STYLE = "moderate"  # Options: "none", "minimal", "moderate", "heavy"
TONE = "professional, scientific"  # Options: "professional", "exciting", "casual", "dramatic"

# Output Settings
SAVE_DRAFTS = True
DRAFTS_FOLDER = "outputs/tweets"

# Database Settings
DATABASE_URL = "postgresql://postgres:SecurePassword@localhost/pwhl_analytics"
