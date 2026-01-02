"""
Feature Engineering for PWHL Game Predictions
Calculates features from historical data for model training
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_models import Game, Team, PlayerGameStats, GoalieGameStats
from database.db_queries import Session
from datetime import datetime, timedelta


def calculate_team_season_stats(team_code, up_to_date=None, last_n_games=None):
    """
    Calculate season-to-date statistics for a team

    Args:
        team_code: Team code (e.g., 'BOS', 'MTL')
        up_to_date: Calculate stats up to this date (for historical predictions)
        last_n_games: If provided, only use last N games instead of full season

    Returns:
        dict: Team statistics including wins, losses, goals, etc.
    """
    # TODO: Implement season stats calculation
    pass


def calculate_rest_days(team_code, game_date):
    """
    Calculate days of rest since team's last game

    Args:
        team_code: Team code
        game_date: Date of upcoming game

    Returns:
        int: Days since last game
    """
    # TODO: Implement rest days calculation
    pass


def calculate_head_to_head_record(team1_code, team2_code, up_to_date=None):
    """
    Calculate head-to-head record between two teams

    Args:
        team1_code: First team code
        team2_code: Second team code
        up_to_date: Calculate record up to this date

    Returns:
        dict: Head-to-head statistics
    """
    # TODO: Implement head-to-head calculation
    pass


def build_game_features(home_team, away_team, game_date):
    """
    Build complete feature set for a game prediction

    Args:
        home_team: Home team code
        away_team: Away team code
        game_date: Date of the game

    Returns:
        dict: Complete feature dictionary for model input
    """
    features = {}

    # TODO: Aggregate all features
    # - Home/away team season stats
    # - Home/away advantage gaps
    # - Rest days for both teams
    # - Head-to-head record
    # - Recent form (last 5-10 games)

    return features
