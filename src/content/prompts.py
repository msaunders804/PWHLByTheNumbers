"""
AI Prompt Templates for Tweet Generation
"""

def build_game_summary_prompt(game_data, hot_players, hot_goalies, firsts=None):
    """
    Build a prompt for AI to generate a game summary tweet

    Args:
        game_data: Dict with game info (teams, score, date, venue)
        hot_players: List of dicts with player performances
        hot_goalies: List of dicts with goalie performances
        firsts: Dict with historical firsts (optional)

    Returns:
        String prompt for the AI
    """

    # Extract key info
    visitor = game_data['visitor_team']
    home = game_data['home_team']
    visitor_score = game_data['visitor_score']
    home_score = game_data['home_score']
    winner = game_data['winner']
    is_takeover = game_data.get('is_takeover', False)
    takeover_city = game_data.get('takeover_city', None)

    prompt = f"""You are writing exciting but data focused social media content for a PWHL analytics account.
Develop the post to display exciting but data focused information about the game in the following format.
Once you have identified the basic information, analyze the game details and create a tweet that highlights the key moments and standout players.
If there are any remarkable stats (including # of attendees), include them in the tweet. You must format the tweet to start with the Game Results as listed below:

Game Result:
{visitor} {visitor_score} @ {home} {home_score}
Winner: {winner}
"""

    # Add takeover game context
    if is_takeover and takeover_city:
        prompt += f"\n🌟 SPECIAL EVENT - This was a TAKEOVER TOUR game in {takeover_city}! This is a neutral-site game, not a regular home game. Make sure to mention this is part of the Takeover Tour in {takeover_city}!\n"

    # Add hot players section
    if hot_players:
        prompt += "\nHot Players:\n"
        for player in hot_players:
            prompt += f"- {player['name']} ({player['team']}) - {', '.join(player['highlights'])}\n"

    # Add hot goalies section
    if hot_goalies:
        prompt += "\nGoalie Performances:\n"
        for goalie in hot_goalies:
            prompt += f"- {goalie['name']} ({goalie['team']}) - {', '.join(goalie['highlights'])}\n"

    # Add firsts section (IMPORTANT!)
    if firsts:
        high_significance_firsts = []

        # Collect high significance firsts
        for first in firsts.get('players', []):
            if first.get('significance') == 'high':
                high_significance_firsts.append(f"- {first['description']} ({first['detail']})")

        for first in firsts.get('goalies', []):
            if first.get('significance') == 'high':
                high_significance_firsts.append(f"- {first['description']} ({first['detail']})")

        for first in firsts.get('teams', {}).get('home', []) + firsts.get('teams', {}).get('away', []):
            if first.get('significance') == 'high':
                high_significance_firsts.append(f"- {first['description']} ({first['detail']})")

        if high_significance_firsts:
            prompt += "\n🎯 CRITICAL - Historical Firsts (MUST MENTION EXACTLY AS WRITTEN):\n"
            prompt += "\n".join(high_significance_firsts)
            prompt += "\n\nIMPORTANT: Use the EXACT wording above for these achievements. If it says 'First hat trick of the season for [Player Name]', DO NOT change it to 'FIRST HAT TRICK OF THE SEASON'. The distinction matters - personal firsts vs league-wide firsts are different!\n"

    # Add instructions for the AI
    prompt += """
Write a tweet that:
1. Is under 280 characters
2. Captures the excitement of the game
3. Highlights the top performer
4. CRITICAL: If there are Historical Firsts listed above, YOU MUST use the EXACT wording provided. Do not embellish or change the phrasing - accuracy is essential!
5. If this is a TAKEOVER TOUR game, YOU MUST mention the city and that it's part of the Takeover Tour!
6. Uses 1-3 relevant emojis
7. Includes #PWHL hashtag
8. Is engaging and shareable

Tweet:"""

    return prompt


def build_hot_player_prompt(player_data, game_context):
    """
    Build a prompt focused on a single standout player
    
    Args:
        player_data: Dict with player stats (name, team, goals, assists, etc.)
        game_context: Dict with game result
    
    Returns:
        String prompt for the AI
    """
    
    # Extract variables first for cleaner f-string
    name = player_data['name']
    jersey = player_data.get('jersey', '')
    team = player_data['team']
    goals = player_data['goals']
    assists = player_data['assists']
    points = player_data['points']
    shots = player_data.get('shots', 0)
    highlights = ', '.join(player_data['highlights'])
    
    visitor = game_context['visitor_team']
    home = game_context['home_team']
    visitor_score = game_context['visitor_score']
    home_score = game_context['home_score']
    
    prompt = f"""You are writing exciting but data focused social media content for a PWHL analytics account.
Focus on highlighting one standout player's performance in a specific game. If a player scores 3 goals (a hat trick) they will automatically be the hot player, unless a player scored more than 3 goals that game.

Player: {name} (#{jersey} {team})
Game Result: {visitor} {visitor_score} @ {home} {home_score}

Player Stats:
- Goals: {goals}
- Assists: {assists}
- Points: {points}
- Shots: {shots}
- Highlights: {highlights}

Write a tweet that:
1. Is under 280 characters
2. Highlights the player's standout performance
3. Uses 1-3 relevant emojis
4. Includes #PWHL hashtag
5. Is engaging and shareable

Tweet:"""
    
    return prompt


def build_goalie_spotlight_prompt(goalie_data, game_context):
    """
    Build a prompt focused on a goalie's performance
    
    Args:
        goalie_data: Dict with goalie stats
        game_context: Dict with game result
    
    Returns:
        String prompt for the AI
    """
    
    # Extract variables
    name = goalie_data['name']
    jersey = goalie_data.get('jersey', '')
    team = goalie_data['team']
    saves = goalie_data['saves']
    save_pct = goalie_data['save_pct']
    goals_against = goalie_data['goals_against']
    time_played = goalie_data.get('time', 'N/A')
    highlights = ', '.join(goalie_data['highlights'])
    
    visitor = game_context['visitor_team']
    home = game_context['home_team']
    visitor_score = game_context['visitor_score']
    home_score = game_context['home_score']
    
    prompt = f"""You are writing exciting but data focused social media content for a PWHL analytics account.
Focus on highlighting one standout goalie's performance in a specific game.

Goalie: {name} (#{jersey} {team})
Game Result: {visitor} {visitor_score} @ {home} {home_score}

Goalie Stats:
- Saves: {saves}
- Save %: {save_pct:.1f}%
- Goals Against: {goals_against}
- Time Played: {time_played}
- Highlights: {highlights}

Write a tweet that:
1. Is under 280 characters
2. Highlights the goalie's standout performance
3. Uses 1-3 relevant emojis
4. Includes #PWHL hashtag
5. Is engaging and shareable

Tweet:"""
    
    return prompt


def build_attendance_highlight_prompt(game_data):
    """
    Build a prompt for highlighting high attendance
    
    Args:
        game_data: Dict with game info including attendance
    
    Returns:
        String prompt for the AI
    """
    
    # Extract data
    visitor = game_data['visitor_team']
    home = game_data['home_team']
    visitor_score = game_data.get('visitor_score', 0)
    home_score = game_data.get('home_score', 0)
    attendance_raw = game_data.get('attendance', 0)
    venue = game_data.get('venue', 'Unknown')
    
    # Parse attendance to int
    try:
        attendance = int(str(attendance_raw).replace(',', ''))
    except:
        attendance = 0
    
    final_score = f"{visitor_score}-{home_score}"
    
    prompt = f"""You are writing exciting but data focused social media content for a PWHL analytics account.
Highlight the impressive fan turnout and attendance at this game.

Game Details:
- {visitor} @ {home}
- Final Score: {final_score}
- Attendance: {attendance:,}
- Venue: {venue}

Write a tweet that:
1. Is under 280 characters
2. Celebrates the crowd and fan support
3. Mentions the attendance number prominently
4. Uses 1-2 relevant emojis (crowds, celebration, fire)
5. Includes #PWHL hashtag
6. Creates excitement about growing fan engagement
7. Makes fans feel part of something special

Tweet:"""
    
    return prompt