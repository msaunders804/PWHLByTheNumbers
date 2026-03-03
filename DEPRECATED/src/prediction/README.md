# PWHL Game Prediction System

Machine learning system for predicting PWHL game outcomes using logistic regression.

## Overview

This prediction system uses historical game data to predict future game outcomes with win probabilities (0-100%). The system is designed to improve accuracy as the season progresses and more games are played.

**Current Status**: Early season (limited data)
- Training data: 18 games from Season 8
- Features: 7 (reduced set for early season)
- Test accuracy: 50% (baseline: 55.4%)
- Model will improve as more games are played

## Files

- **[feature_engineering.py](feature_engineering.py)** - Calculates predictive features from historical data
- **[model.py](model.py)** - Trains and evaluates the logistic regression model
- **[predict.py](predict.py)** - Interface for making predictions on upcoming games

## Quick Start

### 1. Train the Model

Train a new model using all available historical data:

```bash
python src/prediction/model.py
```

This will:
- Collect all completed Season 8 games
- Calculate features for each game (using only data from before the game date)
- Train a logistic regression model
- Evaluate accuracy on a test set
- Save the model to `data/models/pwhl_model.pkl`

**Recommendation**: Retrain weekly as new games are played to improve accuracy.

### 2. Make Predictions

#### Predict a single game:
```bash
python src/prediction/predict.py --home 5 --away 3 --date 2026-01-05
```

#### Predict all games this week:
```bash
python src/prediction/predict.py --this-week
```

#### Predict upcoming games and save to file:
```bash
python src/prediction/predict.py --this-week --save
```

#### Predict games in next 14 days:
```bash
python src/prediction/predict.py --upcoming --days 14
```

## Features Used

The model currently uses 7 features (reduced set for early season):

1. **home_goals_per_game** - Home team's offensive strength
2. **away_goals_per_game** - Away team's offensive strength
3. **home_goals_against_per_game** - Home team's defensive strength
4. **away_goals_against_per_game** - Away team's defensive strength
5. **away_goal_differential** - Away team's net goals per game
6. **home_h2h_win_pct** - Historical matchup record
7. **away_win_pct_on_road** - Away team's road performance

**When 50+ games are available**, the model can be upgraded to use the full 15-feature set by changing `feature_set='reduced'` to `feature_set='full'` in both [model.py](model.py:130) and [predict.py](predict.py:104).

## How It Works

### Data Leakage Prevention

**CRITICAL CONCEPT**: The model only uses data from BEFORE the prediction date.

For example, when predicting a game on Jan 20:
- ✓ Uses team stats from games played before Jan 20
- ✗ Does NOT use the game being predicted
- ✗ Does NOT use any games after Jan 20

This ensures the model learns real patterns, not "future information."

### Feature Engineering

Raw data (game scores, dates) is transformed into meaningful features:

```python
# Instead of: "Team scored 3, 2, 4 goals"
# We calculate: "Team averages 3.0 goals per game"

features = get_game_features(
    home_team_id=5,
    away_team_id=3,
    game_date=datetime(2026, 1, 20).date(),
    season_id=8,
    feature_set='reduced'
)
```

### Model Training

The logistic regression model learns optimal weights for each feature:

```
P(home win) = sigmoid(
    w1 * home_goals_per_game +
    w2 * away_goals_against_per_game +
    ... +
    w7 * away_win_pct_on_road
)
```

The model finds weights that maximize prediction accuracy on historical games.

### Train/Test Split

Data is split 80/20:
- **Training set** (80%): Model learns from these games
- **Test set** (20%): Model is evaluated on these unseen games

This prevents overfitting and shows how well the model generalizes.

## Prediction Output

Example prediction output:

```
PREDICTING GAME: Minnesota Frost @ Boston Fleet
Date: 2026-01-03

PREDICTION:
  Minnesota Frost (Away): 26.3% win probability
  Boston Fleet (Home): 73.7% win probability

  Predicted Winner: Boston Fleet (Home)
  Confidence: 73.7%

KEY FACTORS:
  Boston Fleet scoring: 2.57 goals/game
  Boston Fleet defense: 1.14 goals allowed/game
  Minnesota Frost scoring: 3.33 goals/game
  Minnesota Frost defense: 1.67 goals allowed/game
  Minnesota Frost road record: 75.0% wins
  Head-to-head: Boston Fleet won 50.0% of previous meetings
```

## Improving Accuracy

The model will naturally improve as the season progresses:

| Games Played | Features | Expected Accuracy |
|--------------|----------|-------------------|
| 10-20 games  | 7 (reduced) | ~50-60% |
| 30-50 games  | 7 (reduced) | ~60-65% |
| 50+ games    | 15 (full)   | ~65-70% |

**Action items**:
1. **Weekly retraining**: Run `python src/prediction/model.py` weekly
2. **Switch to full features**: When 50+ games are available, change `feature_set='reduced'` to `feature_set='full'`
3. **Track accuracy**: Monitor test accuracy over time

## Team IDs

Current Season 8 teams:

| ID | Team | Code |
|----|------|------|
| 1  | Boston Fleet | BOS |
| 2  | Minnesota Frost | MIN |
| 3  | Montréal Victoire | MTL |
| 4  | New York Sirens | NY |
| 5  | Ottawa Charge | OTT |
| 6  | Toronto Sceptres | TOR |
| 8  | Seattle Torrent | SEA |
| 9  | Vancouver Goldeneyes | VAN |

## Integration with Pipeline

To add weekly predictions to your Twitter pipeline:

1. Update the database with latest games:
   ```bash
   python scripts/update_database.py
   ```

2. Retrain the model:
   ```bash
   python src/prediction/model.py
   ```

3. Generate predictions for upcoming week:
   ```bash
   python src/prediction/predict.py --this-week --save
   ```

4. The predictions will be saved to `outputs/predictions/` as JSON

5. (Future) Create a tweet generator that formats these predictions for Twitter

## Learning Resources

**Key ML Concepts Used**:
- **Logistic Regression**: Outputs probabilities (0-100%) instead of just yes/no
- **Feature Engineering**: Converting raw data into meaningful inputs
- **Cross-Validation**: Splitting data to test model on unseen games
- **Regularization**: Preventing overfitting (built into sklearn's LogisticRegression)
- **Curse of Dimensionality**: Need 10-20 examples per feature for reliable learning

**Why Logistic Regression?**
- Interpretable: Can see which features matter most
- Probabilistic: Outputs confidence levels, not just predictions
- Fast: Trains in seconds, not minutes
- Reliable: Well-understood algorithm with decades of research

## Troubleshooting

**"Model didn't beat baseline"**: Normal for early season! Retrain as more games are played.

**"Test accuracy is 50%"**: The model is essentially guessing. Need more games for reliable patterns.

**Counterintuitive feature weights**: With limited data, the model may find spurious correlations. This will improve with more data.

**No upcoming games found**: The database only has completed games. For testing, use manual predictions with `--home --away --date`.

## Next Steps

1. ✓ Build prediction interface
2. ✓ Test predictions
3. ⏳ Retrain weekly as season progresses
4. ⏳ Create tweet generator for predictions
5. ⏳ Integrate with pipeline for Sunday posts
6. ⏳ Switch to full feature set when 50+ games available
7. ⏳ Add confidence intervals to predictions
8. ⏳ Track prediction accuracy over time
