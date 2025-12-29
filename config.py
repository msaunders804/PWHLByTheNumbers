"""
Configuration for AI Tweet Generator
Stores API keys and settings
"""

AI_PROVIDER = "anthropic"  # Fill this in

# API Keys - Get these from:
# Anthropic: https://console.anthropic.com/
ANTHROPIC_API_KEY = ""  # Your Claude API key here

# AI Model Selection
CLAUDE_MODEL = "claude-sonnet-4-20250514"  # Latest Claude model

# Tweet Settings
MAX_TWEET_LENGTH = 280
INCLUDE_HASHTAGS = True
BRAND_HASHTAGS = ["#PWHL"]  # Add more if you want

# Content Settings
EMOJI_STYLE = "moderate"  # Options: "none", "minimal", "moderate", "heavy"
TONE = "exciting"  # Options: "professional", "exciting", "casual", "dramatic"

# Output Settings
SAVE_DRAFTS = True
DRAFTS_FOLDER = "tweet_drafts"