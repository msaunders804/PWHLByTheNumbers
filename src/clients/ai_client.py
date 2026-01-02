"""
AI Client - Communicates with Claude or GPT
"""

import json
from config import *

def call_ai(prompt, provider=AI_PROVIDER):
    """
    Send prompt to AI and get response
    
    Args:
        prompt: String prompt to send
        provider: Which AI to use ("anthropic", "openai", or "test")
    
    Returns:
        String response from AI
    """
    
    if provider == "test":
        # Test mode - return fake tweet
        return "🏒 FINAL: BOS 4, MIN 3! Sarah Nurse with the hat trick! 🔥 #PWHL"
    
    elif provider == "anthropic":
        # TODO #8: Implement Claude API call
        # You'll need to:
        # 1. Import the anthropic library
        # 2. Create a client with your API key
        # 3. Send a message with the prompt
        # 4. Extract and return the text response
        
        # Hint: Check Anthropic docs at https://docs.anthropic.com/
        
        import anthropic
        
        # Create client
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) # Initialize Anthropic client with API key
        
        # Send message
        message = client.messages.create(
            model=CLAUDE_MODEL,  # Which model? (see config.py)
            max_tokens=124,  # How many tokens for a tweet? (~100-150)
            messages=[
                {"role": "user", "content": prompt}  # Fill in role and content
            ]
        )
        
        # Extract text
        response_text = message.content[0].text  # How do you get text from the message?
        
        return response_text

def validate_tweet(tweet_text, max_length=MAX_TWEET_LENGTH):
    """
    Check if tweet meets requirements
    
    Args:
        tweet_text: The generated tweet
        max_length: Maximum characters allowed
    
    Returns:
        Tuple: (is_valid: bool, issues: list of strings)
    """
    
    issues = []
    
    # TODO #10: Check tweet length
    if len(tweet_text) > 280:  # What's the limit?
        issues.append(f"Tweet too long: {len(tweet_text)} chars")
    
    # TODO #11: Check for required hashtag
    if "#PWHL" not in tweet_text:  # Where should we check?
        issues.append("Missing #PWHL hashtag")
    
    # TODO #12: Check for empty tweet
    if not tweet_text or tweet_text.strip() == "":
        issues.append("Tweet is empty")
    
    # TODO #13: Check for placeholder text (sometimes AI leaves these)
    placeholders = ["[", "]", "TODO", "FILL"]
    for placeholder in placeholders:
        if placeholder in tweet_text:  # How do we check if placeholder exists?
            issues.append(f"Contains placeholder: {placeholder}")
    
    is_valid = len(issues) == 0
    
    return is_valid, issues