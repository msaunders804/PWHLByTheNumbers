"""
Configuration for AI Tweet Generator
Stores API keys and settings
"""

AI_PROVIDER = "anthropic"  # Fill this in

# API Keys - Get these from:
# Anthropic: https://console.anthropic.com/
ANTHROPIC_API_KEY = "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"  # Your Claude API key here

# AI Model Selection
CLAUDE_MODEL = "claude-sonnet-4-20250514"  # Latest Claude model

# Tweet Settings
MAX_TWEET_LENGTH = 280
INCLUDE_HASHTAGS = True
BRAND_HASHTAGS = ["#PWHL"]  # Add more if you want
TWITTER_ENABLED = True
TWITTER_API_KEY = "RjUsyQbXGlNI3kb5z5dvVeNiP"
TWITTER_API_SECRET = "ubQo31cczF6AsWHVSMPKfpxIt4BP00cX4B6BvAKH65wotOM6iG"
TWITTER_ACCESS_TOKEN = "2004580448220200961-sJgQKw9nAo5QRe4yMp9WcYsp3nxej7"
TWITTER_ACCESS_TOKEN_SECRET = "pFl6deSnNPk4BkOD4owL4EcOETS1pHJnGcHSjL7m"

# Content Settings
EMOJI_STYLE = "moderate"  # Options: "none", "minimal", "moderate", "heavy"
TONE = "professional, scientific"  # Options: "professional", "exciting", "casual", "dramatic"

# Output Settings
SAVE_DRAFTS = True
DRAFTS_FOLDER = "tweet_drafts"