"""
PWHL Game Prediction Interface
Functions to make predictions for upcoming games
"""

import sys
import os
import json
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prediction.model import PWHLPredictionModel
from prediction.feature_engineering import build_game_features


def predict_game(home_team, away_team, game_date, model_path=None):
    """
    Predict the outcome of a single game

    Args:
        home_team: Home team code (e.g., 'BOS')
        away_team: Away team code (e.g., 'MTL')
        game_date: Date of the game (datetime object or string)
        model_path: Path to saved model (if None, uses default)

    Returns:
        dict: Prediction results with probabilities and recommended pick
    """
    # Load model
    if model_path is None:
        model_path = os.path.join('data', 'models', 'pwhl_predictor.pkl')

    model = PWHLPredictionModel.load(model_path)

    # Build features
    features = build_game_features(home_team, away_team, game_date)

    # TODO: Convert features dict to numpy array in correct order
    # X = convert_features_to_array(features, model.feature_names)

    # Make prediction
    # prediction = model.predict(X)[0]
    # probabilities = model.predict_proba(X)[0]

    # TODO: Return formatted prediction
    result = {
        'home_team': home_team,
        'away_team': away_team,
        'game_date': str(game_date),
        'predicted_winner': None,  # home_team if prediction == 1 else away_team
        'home_win_probability': None,  # probabilities[1]
        'away_win_probability': None,  # probabilities[0]
        'confidence': None,  # max(probabilities)
    }

    return result


def predict_weekly_games(start_date, end_date, model_path=None):
    """
    Predict all games in a given week

    Args:
        start_date: Start of prediction period
        end_date: End of prediction period
        model_path: Path to saved model

    Returns:
        list: Predictions for all games in the period
    """
    # TODO: Query schedule for games in date range
    # TODO: Predict each game
    # TODO: Format results for Twitter posting

    predictions = []

    return predictions
