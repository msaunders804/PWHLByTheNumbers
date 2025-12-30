"""
Configuration for AI Tweet Generator
Stores API keys and settings
"""

AI_PROVIDER = "anthropic"  # Fill this in

# API Keys - Get these from:


# Content Settings
EMOJI_STYLE = "moderate"  # Options: "none", "minimal", "moderate", "heavy"
TONE = "professional, scientific"  # Options: "professional", "exciting", "casual", "dramatic"

# Output Settings
SAVE_DRAFTS = True
DRAFTS_FOLDER = "tweet_drafts"