import requests

BASE_URL = "https://lscluster.hockeytech.com/feed/index.php"
PARAMS = {
    "key": "446521baf8c38984",
    "client_code": "pwhl"
}

def fetch_game_summary(game_id):
    """Fetch complete game summary including player stats"""
    params = {
        **PARAMS,
        "feed": "gc",
        "tab": "gamesummary",
        "game_id": game_id
    }
    response = requests.get(BASE_URL, params=params)
    response.raise_for_status()
    return response.json()

def fetch_season_schedule(season_id=8):
    """Fetch all games for a season"""
    params = {
        **PARAMS,
        "feed": "modulekit",
        "view": "schedule",
        "season_id": season_id
    }
    response = requests.get(BASE_URL, params=params)
    response.raise_for_status()
    return response.json()

def fetch_teams(season_id=8):
    """Fetch all teams for a season"""
    params = {
        **PARAMS,
        "feed": "modulekit",
        "view": "teamsbyseason",
        "season_id": season_id
    }
    response = requests.get(BASE_URL, params=params)
    response.raise_for_status()
    return response.json()

# Test it
if __name__ == "__main__":
    # Test with a recent completed game
    schedule = fetch_season_schedule()
    games = schedule['SiteKit']['Schedule']
    
    # Find first completed game
    completed_game = next(g for g in games if g['game_status'] == 'Final')
    print(f"Testing with game {completed_game['id']}")
    
    # Fetch that game's data
    game_data = fetch_game_summary(completed_game['id'])
    summary = game_data['GC']['Gamesummary']
    
    import json
    
    print("\n=== HOME SKATERS (first player) ===")
    home_skaters = summary['home_team_lineup']['players']
    print(json.dumps(home_skaters[0], indent=2))
    
    print("\n=== VISITOR SKATERS (first player) ===")
    visitor_skaters = summary['visitor_team_lineup']['players']
    print(json.dumps(visitor_skaters[0], indent=2))