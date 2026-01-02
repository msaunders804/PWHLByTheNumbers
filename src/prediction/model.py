"""
PWHL Game Prediction Model
Machine learning model for predicting game outcomes
"""

import sys
import os
import json
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import pickle


class PWHLPredictionModel:
    """
    PWHL game outcome prediction model
    """

    def __init__(self, model_type='logistic_regression'):
        """
        Initialize the prediction model

        Args:
            model_type: Type of model ('logistic_regression', 'random_forest')
        """
        self.model_type = model_type
        self.model = None
        self.feature_names = []
        self.trained_date = None

        if model_type == 'logistic_regression':
            self.model = LogisticRegression(max_iter=1000)
        elif model_type == 'random_forest':
            self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        else:
            raise ValueError(f"Unknown model type: {model_type}")

    def train(self, X, y, feature_names=None):
        """
        Train the model on historical data

        Args:
            X: Feature matrix (n_samples, n_features)
            y: Target labels (1 = home win, 0 = away win)
            feature_names: List of feature names for interpretability
        """
        if feature_names:
            self.feature_names = feature_names

        self.model.fit(X, y)
        self.trained_date = datetime.now().isoformat()

        print(f"Model trained on {len(X)} games")
        print(f"Training accuracy: {self.model.score(X, y):.3f}")

    def predict(self, X):
        """
        Predict game outcomes

        Args:
            X: Feature matrix

        Returns:
            array: Predicted labels (1 = home win, 0 = away win)
        """
        return self.model.predict(X)

    def predict_proba(self, X):
        """
        Predict win probabilities

        Args:
            X: Feature matrix

        Returns:
            array: Probabilities [away_win_prob, home_win_prob]
        """
        return self.model.predict_proba(X)

    def save(self, filepath):
        """
        Save model to disk

        Args:
            filepath: Path to save model file
        """
        model_data = {
            'model': self.model,
            'model_type': self.model_type,
            'feature_names': self.feature_names,
            'trained_date': self.trained_date
        }

        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)

        print(f"Model saved to {filepath}")

    @classmethod
    def load(cls, filepath):
        """
        Load model from disk

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

        print(f"Model loaded from {filepath}")
        print(f"Trained on: {instance.trained_date}")

        return instance
