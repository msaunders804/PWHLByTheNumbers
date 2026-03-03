"""
PWHL Game Prediction Interface
Generate win probability predictions for upcoming games

Usage Examples:
    # Predict a single game
    python predict.py --home 5 --away 3 --date 2025-01-05

    # Predict all games this week
    python predict.py --this-week

    # Predict all upcoming games
    python predict.py --upcoming
"""

import sys
import os
from datetime import datetime, timedelta
import argparse

# Add project root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.db_models import Game, Team
from src.prediction.model import PWHLPredictionModel
from src.prediction.feature_engineering import get_game_features

# Database configuration
DATABASE_URL = 'postgresql://postgres:SecurePassword@localhost/pwhl_analytics'
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


def load_trained_model(model_path='data/models/pwhl_model.pkl'):
    """
    Load the trained model from disk

    Returns:
        PWHLPredictionModel instance or None if model doesn't exist
    """
    if not os.path.exists(model_path):
        print(f"[ERROR] No trained model found at {model_path}")
        print("Please train a model first by running: python src/prediction/model.py")
        return None

    try:
        model = PWHLPredictionModel.load(model_path)
        return model
    except Exception as e:
        print(f"[ERROR] Failed to load model: {e}")
        return None


def get_team_name(team_id, session):
    """Get team name from team ID"""
    team = session.query(Team).filter(Team.team_id == team_id).first()
    if team:
        return team.team_name
    return f"Team {team_id}"


def predict_single_game(home_team_id, away_team_id, game_date, season_id=8, model=None):
    """
    Predict outcome of a single game

    Args:
        home_team_id: Home team ID
        away_team_id: Away team ID
        game_date: Date of game (datetime.date object)
        season_id: Season ID (default: 8)
        model: Trained model (if None, will load from disk)

    Returns:
        Dictionary with prediction results
    """
    # Load model if not provided
    if model is None:
        model = load_trained_model()
        if model is None:
            return None

    session = Session()

    try:
        # Get team names
        home_team_name = get_team_name(home_team_id, session)
        away_team_name = get_team_name(away_team_id, session)

        print(f"\n{'='*80}")
        print(f"PREDICTING GAME: {away_team_name} @ {home_team_name}")
        print(f"Date: {game_date}")
        print(f"{'='*80}\n")

        # Calculate features for this matchup
        features = get_game_features(
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            game_date=game_date,
            season_id=season_id,
            feature_set='reduced'  # Use same feature set as training
        )

        # Convert to numpy array in correct order
        feature_vector = np.array([[features[name] for name in model.feature_names]])

        # Get prediction (0 or 1)
        prediction = model.predict(feature_vector)[0]

        # Get win probabilities
        probabilities = model.predict_proba(feature_vector)[0]
        away_win_prob = probabilities[0]
        home_win_prob = probabilities[1]

        # Display results
        print("PREDICTION:")
        print(f"  {away_team_name} (Away): {away_win_prob*100:.1f}% win probability")
        print(f"  {home_team_name} (Home): {home_win_prob*100:.1f}% win probability")
        print()

        if prediction == 1:
            print(f"  Predicted Winner: {home_team_name} (Home)")
        else:
            print(f"  Predicted Winner: {away_team_name} (Away)")

        print(f"\n  Confidence: {max(home_win_prob, away_win_prob)*100:.1f}%")

        # Show key features
        print(f"\n{'='*80}")
        print("KEY FACTORS:")
        print(f"{'='*80}")
        print(f"  {home_team_name} scoring: {features['home_goals_per_game']:.2f} goals/game")
        print(f"  {home_team_name} defense: {features['home_goals_against_per_game']:.2f} goals allowed/game")
        print(f"  {away_team_name} scoring: {features['away_goals_per_game']:.2f} goals/game")
        print(f"  {away_team_name} defense: {features['away_goals_against_per_game']:.2f} goals allowed/game")
        print(f"  {away_team_name} road record: {features['away_win_pct_on_road']*100:.1f}% wins")
        print(f"  Head-to-head: {home_team_name} won {features['home_h2h_win_pct']*100:.1f}% of previous meetings")

        result = {
            'home_team_id': home_team_id,
            'away_team_id': away_team_id,
            'home_team_name': home_team_name,
            'away_team_name': away_team_name,
            'game_date': str(game_date),
            'home_win_probability': float(home_win_prob),
            'away_win_probability': float(away_win_prob),
            'predicted_winner': home_team_name if prediction == 1 else away_team_name,
            'confidence': float(max(home_win_prob, away_win_prob)),
            'features': features
        }

        return result

    finally:
        session.close()


def get_upcoming_games(days_ahead=7, season_id=8):
    """
    Get upcoming games from the database

    Args:
        days_ahead: How many days ahead to look (default: 7 for one week)
        season_id: Season ID

    Returns:
        List of upcoming games
    """
    session = Session()

    try:
        today = datetime.now().date()
        end_date = today + timedelta(days=days_ahead)

        # Find games in date range that haven't been played yet
        upcoming = session.query(Game).filter(
            Game.season_id == season_id,
            Game.date >= today,
            Game.date <= end_date,
            Game.game_status != 'final'  # Not completed yet
        ).order_by(Game.date).all()

        return upcoming

    finally:
        session.close()


def predict_upcoming_games(days_ahead=7, season_id=8):
    """
    Predict all upcoming games in the next N days

    Args:
        days_ahead: How many days ahead to look
        season_id: Season ID

    Returns:
        List of prediction results
    """
    # Load model once
    model = load_trained_model()
    if model is None:
        return []

    # Get upcoming games
    upcoming_games = get_upcoming_games(days_ahead, season_id)

    if not upcoming_games:
        print(f"\n[INFO] No upcoming games found in the next {days_ahead} days")
        return []

    print(f"\n{'='*80}")
    print(f"FOUND {len(upcoming_games)} UPCOMING GAMES")
    print(f"{'='*80}")

    results = []

    for game in upcoming_games:
        result = predict_single_game(
            home_team_id=game.home_team_id,
            away_team_id=game.away_team_id,
            game_date=game.date,
            season_id=season_id,
            model=model
        )

        if result:
            results.append(result)

    return results


def generate_prediction_summary(predictions):
    """
    Generate a formatted summary of predictions
    Useful for creating weekly prediction posts

    Args:
        predictions: List of prediction results

    Returns:
        String with formatted summary
    """
    if not predictions:
        return "No predictions to summarize"

    summary = []
    summary.append("\n" + "="*80)
    summary.append("WEEKLY PREDICTIONS SUMMARY")
    summary.append("="*80)
    summary.append("")

    # Group by date
    by_date = {}
    for pred in predictions:
        date = pred['game_date']
        if date not in by_date:
            by_date[date] = []
        by_date[date].append(pred)

    # Format each day
    for date in sorted(by_date.keys()):
        games = by_date[date]
        summary.append(f"\n{date}:")
        summary.append("-" * 80)

        for pred in games:
            away = pred['away_team_name']
            home = pred['home_team_name']
            winner = pred['predicted_winner']
            confidence = pred['confidence'] * 100

            summary.append(f"  {away} @ {home}")
            summary.append(f"  Prediction: {winner} ({confidence:.1f}% confidence)")
            summary.append(f"  Win Probability: {home} {pred['home_win_probability']*100:.1f}% | {away} {pred['away_win_probability']*100:.1f}%")
            summary.append("")

    summary.append("="*80)
    summary.append(f"Model Accuracy: Check model.py output for latest test accuracy")
    summary.append("Note: Predictions improve as more games are played throughout the season")
    summary.append("="*80)

    return "\n".join(summary)


def save_predictions(predictions, output_dir='outputs/predictions'):
    """
    Save predictions to JSON file

    Args:
        predictions: List of prediction results
        output_dir: Directory to save predictions

    Returns:
        Path to saved file
    """
    import json

    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{output_dir}/predictions_{timestamp}.json"

    output = {
        'timestamp': datetime.now().isoformat(),
        'model_path': 'data/models/pwhl_model.pkl',
        'predictions': predictions
    }

    with open(filename, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n[SAVED] Predictions saved to {filename}")

    return filename


def main():
    parser = argparse.ArgumentParser(description='PWHL Game Prediction Tool')

    # Single game prediction
    parser.add_argument('--home', type=int, help='Home team ID')
    parser.add_argument('--away', type=int, help='Away team ID')
    parser.add_argument('--date', type=str, help='Game date (YYYY-MM-DD)')

    # Batch predictions
    parser.add_argument('--this-week', action='store_true',
                       help='Predict all games in the next 7 days')
    parser.add_argument('--upcoming', action='store_true',
                       help='Predict all upcoming games in database')
    parser.add_argument('--days', type=int, default=7,
                       help='Number of days ahead to predict (default: 7)')

    # Output options
    parser.add_argument('--save', action='store_true',
                       help='Save predictions to JSON file')

    args = parser.parse_args()

    print("="*80)
    print("PWHL GAME PREDICTION TOOL")
    print("="*80)

    # Single game prediction
    if args.home and args.away and args.date:
        game_date = datetime.strptime(args.date, '%Y-%m-%d').date()

        result = predict_single_game(
            home_team_id=args.home,
            away_team_id=args.away,
            game_date=game_date
        )

        if result and args.save:
            save_predictions([result])

    # Weekly predictions
    elif args.this_week or args.upcoming:
        predictions = predict_upcoming_games(days_ahead=args.days)

        if predictions:
            # Print summary
            summary = generate_prediction_summary(predictions)
            print(summary)

            # Save if requested
            if args.save:
                save_predictions(predictions)

    else:
        # No arguments - show help
        parser.print_help()
        print("\n" + "="*80)
        print("EXAMPLES:")
        print("="*80)
        print("  # Predict a single game")
        print("  python src/prediction/predict.py --home 5 --away 3 --date 2025-01-05")
        print()
        print("  # Predict all games this week")
        print("  python src/prediction/predict.py --this-week")
        print()
        print("  # Predict upcoming games and save to file")
        print("  python src/prediction/predict.py --this-week --save")
        print()
        print("  # Predict games in next 14 days")
        print("  python src/prediction/predict.py --upcoming --days 14")
        print("="*80)


if __name__ == "__main__":
    main()
