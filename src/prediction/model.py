"""
PWHL Game Prediction Model
Machine learning model for predicting game outcomes using Logistic Regression

Learning Goals:
- Understand how logistic regression learns from historical data
- See how features are converted to predictions
- Learn about train/test splits and model evaluation
"""

import sys
import os
import json
import numpy as np
from datetime import datetime

# Add project root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
import pickle

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.db_models import Game
from src.prediction.feature_engineering import get_game_features

# Database configuration
DATABASE_URL = 'postgresql://postgres:SecurePassword@localhost/pwhl_analytics'
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


class PWHLPredictionModel:
    """
    PWHL game outcome prediction model using Logistic Regression

    This model learns patterns from historical games to predict future outcomes.
    It's called "logistic" because it outputs probabilities (0-100%) instead of
    just yes/no predictions.
    """

    def __init__(self, model_type='logistic_regression'):
        """
        Initialize the prediction model

        Args:
            model_type: Type of model (default: 'logistic_regression')
                       For now we'll stick with logistic regression for interpretability
        """
        self.model_type = model_type
        self.model = None
        self.feature_names = []
        self.trained_date = None
        self.training_accuracy = None
        self.test_accuracy = None

        # Create logistic regression model
        # max_iter=1000 means it will try up to 1000 iterations to find best weights
        # random_state=42 ensures reproducible results (same results every time)
        self.model = LogisticRegression(max_iter=1000, random_state=42)

    def collect_training_data(self, season_id=8, min_games_played=5):
        """
        Collect historical games from database and convert to features

        This is CRITICAL: We must ensure no data leakage!
        For each game, we only use features calculated from games BEFORE that date.

        Args:
            season_id: Which season to train on (default: 8, current season)
            min_games_played: Skip early season games where teams have <N games
                             (not enough data for reliable features)

        Returns:
            X: Feature matrix (numpy array of shape [n_games, n_features])
            y: Target labels (numpy array of 1s and 0s)
               1 = home team won, 0 = away team won
            game_ids: List of game IDs for reference
        """
        print("=" * 80)
        print("COLLECTING TRAINING DATA")
        print("=" * 80)

        session = Session()

        try:
            # Get all completed games from this season, ordered by date
            games = session.query(Game).filter(
                Game.season_id == season_id,
                Game.game_status == 'final'
            ).order_by(Game.date).all()

            print(f"Found {len(games)} completed games in season {season_id}")

            X_data = []  # Will hold feature vectors
            y_data = []  # Will hold outcomes (1=home win, 0=away win)
            game_ids = []

            skipped_early = 0

            for game in games:
                # Check if both teams have played enough games
                # This prevents predictions based on <5 games of data
                home_games_before = session.query(Game).filter(
                    Game.season_id == season_id,
                    Game.date < game.date,
                    ((Game.home_team_id == game.home_team_id) | (Game.away_team_id == game.home_team_id))
                ).count()

                away_games_before = session.query(Game).filter(
                    Game.season_id == season_id,
                    Game.date < game.date,
                    ((Game.home_team_id == game.away_team_id) | (Game.away_team_id == game.away_team_id))
                ).count()

                if home_games_before < min_games_played or away_games_before < min_games_played:
                    skipped_early += 1
                    continue  # Skip early season games

                # Calculate features for this game (using only data BEFORE game date)
                try:
                    features = get_game_features(
                        home_team_id=game.home_team_id,
                        away_team_id=game.away_team_id,
                        game_date=game.date,
                        season_id=season_id,
                        feature_set='reduced'  # Use 7 features for early season
                    )

                    # Convert feature dict to ordered list of values
                    # IMPORTANT: Order must be consistent across all games!
                    if not self.feature_names:
                        # First game - save feature order
                        self.feature_names = list(features.keys())

                    feature_vector = [features[name] for name in self.feature_names]

                    # Determine outcome: 1 if home won, 0 if away won
                    home_won = 1 if game.home_score > game.away_score else 0

                    X_data.append(feature_vector)
                    y_data.append(home_won)
                    game_ids.append(game.game_id)

                except Exception as e:
                    print(f"  [WARNING] Skipped game {game.game_id}: {e}")
                    continue

            # Convert to numpy arrays (required format for scikit-learn)
            X = np.array(X_data)
            y = np.array(y_data)

            print(f"\n[OK] Collected {len(X)} games for training")
            print(f"     (Skipped {skipped_early} early-season games with <{min_games_played} games played)")
            print(f"     Features per game: {len(self.feature_names)}")
            print(f"     Home wins: {sum(y)} ({sum(y)/len(y)*100:.1f}%)")
            print(f"     Away wins: {len(y)-sum(y)} ({(len(y)-sum(y))/len(y)*100:.1f}%)")

            return X, y, game_ids

        finally:
            session.close()

    def train(self, X, y, test_size=0.2):
        """
        Train the logistic regression model on historical data

        Args:
            X: Feature matrix (n_samples, n_features)
            y: Target labels (1 = home win, 0 = away win)
            test_size: Fraction of data to hold out for testing (default: 20%)

        The model learns weights for each feature that maximize prediction accuracy.
        """
        print("\n" + "=" * 80)
        print("TRAINING LOGISTIC REGRESSION MODEL")
        print("=" * 80)

        # Split data into training and test sets
        # WHY? To see how well the model generalizes to unseen games
        # shuffle=False preserves chronological order (earlier games in train, later in test)
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, shuffle=False, random_state=42
        )

        print(f"\nTraining set: {len(X_train)} games")
        print(f"Test set:     {len(X_test)} games")

        # TRAIN THE MODEL - This is where the magic happens!
        # The model finds optimal weights for each feature
        print("\n[TRAINING] Finding optimal feature weights...")
        self.model.fit(X_train, y_train)

        # Evaluate on training data
        train_predictions = self.model.predict(X_train)
        self.training_accuracy = accuracy_score(y_train, train_predictions)

        # Evaluate on test data (games the model hasn't seen!)
        test_predictions = self.model.predict(X_test)
        self.test_accuracy = accuracy_score(y_test, test_predictions)

        self.trained_date = datetime.now().isoformat()

        print(f"\n[RESULTS]")
        print(f"Training Accuracy: {self.training_accuracy:.3f} ({self.training_accuracy*100:.1f}%)")
        print(f"Test Accuracy:     {self.test_accuracy:.3f} ({self.test_accuracy*100:.1f}%)")

        # Show detailed test set metrics
        print("\n" + "=" * 80)
        print("DETAILED TEST SET EVALUATION")
        print("=" * 80)
        print(classification_report(y_test, test_predictions,
                                   target_names=['Away Win', 'Home Win']))

        # Confusion matrix shows types of errors
        cm = confusion_matrix(y_test, test_predictions)
        print("Confusion Matrix:")
        print(f"                 Predicted Away  Predicted Home")
        print(f"Actually Away:   {cm[0][0]:>14}  {cm[0][1]:>14}")
        print(f"Actually Home:   {cm[1][0]:>14}  {cm[1][1]:>14}")

        print(f"\n[OK] Model training complete!")

        return X_train, X_test, y_train, y_test

    def show_feature_importance(self):
        """
        Show which features matter most for predictions

        This is one of the big advantages of logistic regression - we can see
        exactly how much each feature influences the prediction!

        Positive weights → higher value increases home win probability
        Negative weights → higher value decreases home win probability
        """
        if self.model is None:
            print("Model not trained yet!")
            return

        print("\n" + "=" * 80)
        print("FEATURE IMPORTANCE (Logistic Regression Coefficients)")
        print("=" * 80)
        print("\nHow to read these:")
        print("  Positive (+) = Feature increases home team win probability")
        print("  Negative (-) = Feature decreases home team win probability")
        print("  Larger magnitude = More important feature")
        print()

        # Get coefficients (weights) for each feature
        coefficients = self.model.coef_[0]

        # Sort by absolute importance
        feature_importance = list(zip(self.feature_names, coefficients))
        feature_importance.sort(key=lambda x: abs(x[1]), reverse=True)

        print(f"{'Feature':<40} {'Weight':>10} {'Impact':>15}")
        print("-" * 80)

        for feature, coef in feature_importance:
            impact = "Favors Home" if coef > 0 else "Favors Away"
            print(f"{feature:<40} {coef:>10.4f} {impact:>15}")

        print("\n" + "=" * 80)

    def predict(self, X):
        """
        Predict game outcomes (0 or 1)

        Args:
            X: Feature matrix

        Returns:
            array: Predicted labels (1 = home win, 0 = away win)
        """
        return self.model.predict(X)

    def predict_proba(self, X):
        """
        Predict win probabilities (0% to 100%)

        Args:
            X: Feature matrix

        Returns:
            array: Probabilities [away_win_prob, home_win_prob] for each game
        """
        return self.model.predict_proba(X)

    def save(self, filepath='data/models/pwhl_model.pkl'):
        """
        Save model to disk so you don't have to retrain every time

        Args:
            filepath: Where to save the model file
        """
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        model_data = {
            'model': self.model,
            'model_type': self.model_type,
            'feature_names': self.feature_names,
            'trained_date': self.trained_date,
            'training_accuracy': self.training_accuracy,
            'test_accuracy': self.test_accuracy
        }

        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)

        print(f"\n[SAVED] Model saved to {filepath}")

    @classmethod
    def load(cls, filepath='data/models/pwhl_model.pkl'):
        """
        Load a previously trained model from disk

        Args:
            filepath: Path to model file

        Returns:
            PWHLPredictionModel: Loaded model instance
        """
        with open(filepath, 'rb') as f:
            model_data = pickle.load(f)

        instance = cls(model_type=model_data['model_type'])
        instance.model = model_data['model']
        instance.feature_names = model_data['feature_names']
        instance.trained_date = model_data['trained_date']
        instance.training_accuracy = model_data.get('training_accuracy')
        instance.test_accuracy = model_data.get('test_accuracy')

        print(f"[LOADED] Model from {filepath}")
        print(f"Trained: {instance.trained_date}")
        print(f"Test Accuracy: {instance.test_accuracy:.3f}")

        return instance


# ============================================================================
# TRAINING SCRIPT - Run this to train your first model!
# ============================================================================

if __name__ == "__main__":
    """
    Train a logistic regression model on Season 8 data

    This script:
    1. Collects all Season 8 games
    2. Calculates features for each game
    3. Trains a logistic regression model
    4. Evaluates accuracy
    5. Shows which features matter most
    6. Saves the model for future use
    """

    print("=" * 80)
    print("PWHL GAME PREDICTION MODEL TRAINER")
    print("=" * 80)
    print("\nThis will train a logistic regression model to predict game outcomes")
    print("based on team statistics, rest days, and matchup history.")
    print()

    # Create model
    model = PWHLPredictionModel()

    # Collect training data from Season 8
    print("[1/4] Collecting training data from database...")
    X, y, game_ids = model.collect_training_data(
        season_id=8,
        min_games_played=2  # Lower threshold to get more training data
    )

    # Train the model
    print("\n[2/4] Training model...")
    X_train, X_test, y_train, y_test = model.train(X, y, test_size=0.2)

    # Show which features are most important
    print("\n[3/4] Analyzing feature importance...")
    model.show_feature_importance()

    # Save the model
    print("\n[4/4] Saving model...")
    model.save('data/models/pwhl_model.pkl')

    print("\n" + "=" * 80)
    print("TRAINING COMPLETE!")
    print("=" * 80)
    print(f"\nFinal Test Accuracy: {model.test_accuracy:.3f} ({model.test_accuracy*100:.1f}%)")
    print(f"Baseline (always pick home): 55.4%")

    if model.test_accuracy > 0.554:
        improvement = (model.test_accuracy - 0.554) * 100
        print(f"\n[SUCCESS] Model beats baseline by {improvement:.1f} percentage points!")
    else:
        print(f"\n[LEARNING OPPORTUNITY] Model didn't beat baseline yet.")
        print("This is normal for a first attempt with limited features!")
        print("Next steps: Add more features or try different feature combinations")

    print("\n[NEXT] You can now use this model to predict future games!")
    print("       See predict.py for examples of making predictions.")
