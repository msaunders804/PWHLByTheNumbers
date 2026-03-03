"""
Feature Engineering for PWHL Game Predictions
Calculates features for machine learning model based on historical data

Key Principle: NEVER use data from the game being predicted (avoid data leakage)
All features use only data from BEFORE the prediction date
"""

import sys
import os
from datetime import datetime, timedelta

# Add project root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from sqlalchemy import create_engine, func, and_, or_
from sqlalchemy.orm import sessionmaker
from src.database.db_models import Game, Team, Player, PlayerGameStats, GoalieGameStats

# Database configuration
DATABASE_URL = 'postgresql://postgres:SecurePassword@localhost/pwhl_analytics'
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


def calculate_team_win_percentage(team_id, before_date, season_id, home_only=False, away_only=False):
    """
    Calculate team's win percentage using only games BEFORE the prediction date

    Args:
        team_id: Team ID to calculate for
        before_date: Only use games before this date (datetime.date object)
        season_id: Season to calculate within
        home_only: Only count home games (default: False)
        away_only: Only count away games (default: False)

    Returns:
        Float between 0.0 and 1.0 (win percentage)
        Returns 0.5 if no games played yet (neutral assumption)

    Example:
        # Predicting a game on 2025-01-20
        win_pct = calculate_team_win_percentage(
            team_id=5,
            before_date=datetime(2025, 1, 20).date(),
            season_id=8
        )
        # Returns 0.667 if team won 4 of 6 games before Jan 20
    """
    session = Session()

    try:
        # Build base query - games before the prediction date
        query = session.query(Game).filter(
            Game.season_id == season_id,
            Game.date < before_date,  # CRITICAL: Only games BEFORE prediction
            Game.game_status == 'final'
        )

        # Filter for home or away games if specified
        if home_only:
            query = query.filter(Game.home_team_id == team_id)
        elif away_only:
            query = query.filter(Game.away_team_id == team_id)
        else:
            # All games (home or away)
            query = query.filter(
                or_(Game.home_team_id == team_id, Game.away_team_id == team_id)
            )

        games = query.all()

        # If no games played yet, return neutral 0.5
        if len(games) == 0:
            return 0.5

        # Count wins
        wins = 0
        for game in games:
            # Check if this team won
            if game.home_team_id == team_id:
                # Team was home
                if game.home_score > game.away_score:
                    wins += 1
            else:
                # Team was away
                if game.away_score > game.home_score:
                    wins += 1

        # Calculate win percentage
        win_pct = wins / len(games)

        return win_pct

    finally:
        session.close()


def calculate_team_goals_per_game(team_id, before_date, season_id, home_only=False, away_only=False, against=False):
    """
    Calculate team's goals per game (or goals against per game)

    Args:
        team_id: Team ID to calculate for
        before_date: Only use games before this date
        season_id: Season to calculate within
        home_only: Only count home games
        away_only: Only count away games
        against: If True, calculate goals AGAINST instead of goals FOR

    Returns:
        Float (average goals per game)
        Returns 2.5 (league average) if no games played yet
    """
    session = Session()

    try:
        query = session.query(Game).filter(
            Game.season_id == season_id,
            Game.date < before_date,
            Game.game_status == 'final'
        )

        if home_only:
            query = query.filter(Game.home_team_id == team_id)
        elif away_only:
            query = query.filter(Game.away_team_id == team_id)
        else:
            query = query.filter(
                or_(Game.home_team_id == team_id, Game.away_team_id == team_id)
            )

        games = query.all()

        if len(games) == 0:
            return 2.5  # League average assumption

        total_goals = 0
        for game in games:
            if game.home_team_id == team_id:
                # Team was home
                if against:
                    total_goals += game.away_score  # Goals against
                else:
                    total_goals += game.home_score  # Goals for
            else:
                # Team was away
                if against:
                    total_goals += game.home_score  # Goals against
                else:
                    total_goals += game.away_score  # Goals for

        return total_goals / len(games)

    finally:
        session.close()


def calculate_days_rest(team_id, game_date, season_id):
    """
    Calculate days of rest since team's last game

    Args:
        team_id: Team ID
        game_date: Date of the game being predicted
        season_id: Season ID

    Returns:
        Integer (days of rest)
        Returns 7 if this is team's first game (assumption)
    """
    session = Session()

    try:
        # Find most recent game BEFORE this game
        last_game = session.query(Game).filter(
            Game.season_id == season_id,
            Game.date < game_date,
            Game.game_status == 'final',
            or_(Game.home_team_id == team_id, Game.away_team_id == team_id)
        ).order_by(Game.date.desc()).first()

        if last_game is None:
            return 7  # First game assumption

        # Calculate days between games
        days_rest = (game_date - last_game.date).days

        return days_rest

    finally:
        session.close()


def calculate_head_to_head_record(team_id, opponent_id, before_date, season_id):
    """
    Calculate team's win percentage against specific opponent

    Args:
        team_id: Team ID
        opponent_id: Opponent team ID
        before_date: Only use games before this date
        season_id: Season ID

    Returns:
        Float (win percentage vs this opponent)
        Returns 0.5 if teams haven't played yet
    """
    session = Session()

    try:
        # Find all games between these two teams
        games = session.query(Game).filter(
            Game.season_id == season_id,
            Game.date < before_date,
            Game.game_status == 'final',
            or_(
                and_(Game.home_team_id == team_id, Game.away_team_id == opponent_id),
                and_(Game.home_team_id == opponent_id, Game.away_team_id == team_id)
            )
        ).all()

        if len(games) == 0:
            return 0.5  # No history - neutral assumption

        wins = 0
        for game in games:
            if game.home_team_id == team_id:
                if game.home_score > game.away_score:
                    wins += 1
            else:
                if game.away_score > game.home_score:
                    wins += 1

        return wins / len(games)

    finally:
        session.close()


def get_game_features(home_team_id, away_team_id, game_date, season_id, feature_set='reduced'):
    """
    Calculate features for a game prediction

    This is the main function you'll call to get features for any game.

    Args:
        home_team_id: Home team ID
        away_team_id: Away team ID
        game_date: Date of the game (datetime.date object)
        season_id: Season ID
        feature_set: 'reduced' (7 features) or 'full' (15 features)
                    Use 'reduced' early season, 'full' when you have 50+ games

    Returns:
        Dictionary with all features for this matchup

    Example:
        features = get_game_features(
            home_team_id=5,
            away_team_id=3,
            game_date=datetime(2025, 1, 20).date(),
            season_id=8,
            feature_set='reduced'
        )
        # Returns: {
        #     'home_goals_per_game': 2.8,
        #     'away_goals_against_per_game': 2.1,
        #     ...
        # }
    """

    print(f"Calculating features for game on {game_date}...")
    print(f"  Home team: {home_team_id}")
    print(f"  Away team: {away_team_id}")

    # Overall team performance
    home_win_pct = calculate_team_win_percentage(home_team_id, game_date, season_id)
    away_win_pct = calculate_team_win_percentage(away_team_id, game_date, season_id)

    # Home/away splits
    home_win_pct_at_home = calculate_team_win_percentage(home_team_id, game_date, season_id, home_only=True)
    away_win_pct_on_road = calculate_team_win_percentage(away_team_id, game_date, season_id, away_only=True)

    # Goals for/against
    home_goals_per_game = calculate_team_goals_per_game(home_team_id, game_date, season_id)
    away_goals_per_game = calculate_team_goals_per_game(away_team_id, game_date, season_id)
    home_goals_against_per_game = calculate_team_goals_per_game(home_team_id, game_date, season_id, against=True)
    away_goals_against_per_game = calculate_team_goals_per_game(away_team_id, game_date, season_id, against=True)

    # Rest days
    home_rest_days = calculate_days_rest(home_team_id, game_date, season_id)
    away_rest_days = calculate_days_rest(away_team_id, game_date, season_id)

    # Head to head
    home_h2h_win_pct = calculate_head_to_head_record(home_team_id, away_team_id, game_date, season_id)

    # Calculate derived features
    home_goal_differential = home_goals_per_game - home_goals_against_per_game
    away_goal_differential = away_goals_per_game - away_goals_against_per_game

    if feature_set == 'reduced':
        # Top 7 most important features (for early season with limited data)
        # Based on logistic regression feature importance analysis
        features = {
            # Offense & Defense (most predictive!)
            'home_goals_per_game': home_goals_per_game,
            'away_goals_per_game': away_goals_per_game,
            'home_goals_against_per_game': home_goals_against_per_game,
            'away_goals_against_per_game': away_goals_against_per_game,

            # Net performance
            'away_goal_differential': away_goal_differential,

            # Matchup history
            'home_h2h_win_pct': home_h2h_win_pct,

            # Road performance
            'away_win_pct_on_road': away_win_pct_on_road,
        }
    else:
        # Full feature set (use when you have 50+ games)
        features = {
            # Overall performance
            'home_win_pct': home_win_pct,
            'away_win_pct': away_win_pct,

            # Home/away splits
            'home_win_pct_at_home': home_win_pct_at_home,
            'away_win_pct_on_road': away_win_pct_on_road,

            # Scoring
            'home_goals_per_game': home_goals_per_game,
            'away_goals_per_game': away_goals_per_game,
            'home_goals_against_per_game': home_goals_against_per_game,
            'away_goals_against_per_game': away_goals_against_per_game,

            # Derived features
            'home_goal_differential': home_goal_differential,
            'away_goal_differential': away_goal_differential,

            # Context
            'home_rest_days': home_rest_days,
            'away_rest_days': away_rest_days,
            'rest_advantage': home_rest_days - away_rest_days,

            # Matchup
            'home_h2h_win_pct': home_h2h_win_pct,
            'away_h2h_win_pct': 1.0 - home_h2h_win_pct,
        }

    print(f"  Calculated {len(features)} features ({feature_set} set)")

    return features


# ============================================================================
# TESTING & EXAMPLES
# ============================================================================

if __name__ == "__main__":
    """
    Test the feature calculations with a real example
    """
    from datetime import datetime

    print("=" * 80)
    print("FEATURE ENGINEERING TEST")
    print("=" * 80)

    # Get a recent game to test with
    session = Session()
    test_game = session.query(Game).filter(
        Game.season_id == 8,
        Game.game_status == 'final'
    ).order_by(Game.date.desc()).first()

    if test_game:
        print(f"\nTesting with Game #{test_game.game_id}")
        print(f"Date: {test_game.date}")
        print(f"Matchup: Team {test_game.away_team_id} @ Team {test_game.home_team_id}")
        print(f"Result: {test_game.away_score} - {test_game.home_score}")
        print()

        # Calculate features as if we were predicting this game
        features = get_game_features(
            home_team_id=test_game.home_team_id,
            away_team_id=test_game.away_team_id,
            game_date=test_game.date,
            season_id=test_game.season_id
        )

        print("\n" + "=" * 80)
        print("CALCULATED FEATURES")
        print("=" * 80)

        for feature_name, value in features.items():
            if isinstance(value, float):
                print(f"{feature_name:.<40} {value:.3f}")
            else:
                print(f"{feature_name:.<40} {value}")

        # Show who should have been predicted to win
        print("\n" + "=" * 80)
        print("SIMPLE PREDICTION (based on win percentage)")
        print("=" * 80)

        home_score = (
            features['home_win_pct'] * 2 +
            features['home_win_pct_at_home'] * 1 +
            features['home_h2h_win_pct'] * 1
        ) / 4

        away_score = (
            features['away_win_pct'] * 2 +
            features['away_win_pct_on_road'] * 1 +
            features['away_h2h_win_pct'] * 1
        ) / 4

        print(f"Home prediction score: {home_score:.3f}")
        print(f"Away prediction score: {away_score:.3f}")

        if home_score > away_score:
            print(f"Prediction: HOME WINS")
        else:
            print(f"Prediction: AWAY WINS")

        actual_winner = "HOME" if test_game.home_score > test_game.away_score else "AWAY"
        print(f"Actual result: {actual_winner} WINS")

        if (home_score > away_score and actual_winner == "HOME") or \
           (away_score > home_score and actual_winner == "AWAY"):
            print("[OK] CORRECT PREDICTION")
        else:
            print("[X] INCORRECT PREDICTION")
    else:
        print("No games found in database")

    session.close()
