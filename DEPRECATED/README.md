# PWHL By The Numbers

Analytics and prediction system for the Professional Women's Hockey League (PWHL).

## Project Structure

```
PWHLByTheNumbers/
├── src/                          # Source code
│   ├── analytics/                # Statistical analysis modules
│   │   ├── home_away_analysis.py # Home vs away performance analysis
│   │   ├── career_stats.py       # Player career statistics
│   │   ├── attendance.py         # Attendance tracking & analysis
│   │   └── team_overview.py      # Team statistics overview
│   ├── database/                 # Database operations
│   │   ├── db_models.py          # SQLAlchemy models
│   │   ├── db_queries.py         # Database query functions
│   │   ├── fetch_data.py         # PWHL API client
│   │   ├── load_data.py          # Data loading to database
│   │   └── setup_db.py           # Database initialization
│   ├── prediction/               # Game prediction models
│   │   ├── feature_engineering.py # Feature calculation
│   │   ├── model.py              # ML model implementation
│   │   └── predict.py            # Prediction interface
│   ├── content/                  # Content generation
│   │   ├── message_gen.py        # AI-powered tweet generation
│   │   ├── prompts.py            # AI prompts
│   │   └── firsts_detector.py    # Historical achievements detector
│   ├── clients/                  # External API clients
│   │   ├── ai_client.py          # Claude AI client
│   │   └── twitter_client.py     # Twitter/X API client
│   ├── visualizers/              # Data visualization
│   │   ├── attendance_visualizations.py
│   │   └── goals_allowed_v_scored.py
│   └── utils/                    # Utilities
│       └── config.py             # Configuration settings
├── scripts/                      # Executable scripts
│   ├── pipeline.py               # Main ETL & posting pipeline
│   └── fetch_career_stats.py     # Career stats fetcher
├── data/                         # Data files
│   ├── raw/                      # Raw data from PWHL API
│   ├── processed/                # Processed data & cached stats
│   └── models/                   # Saved ML models
├── outputs/                      # Generated outputs
│   ├── tweets/                   # Tweet drafts
│   ├── visualizations/           # Charts & graphs
│   └── logs/                     # Pipeline logs
├── config.py                     # Main configuration file
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

## Features

### Analytics
- **Home/Away Analysis**: Team-specific home ice advantage calculations
- **Career Statistics**: Season-to-date and career player stats
- **Attendance Tracking**: Game attendance trends and records
- **Historical Firsts**: Automatic detection of notable achievements

### Prediction (New!)
- **Game Outcome Prediction**: ML models to predict PWHL game winners
- **Win Probability Estimates**: Confidence scores for predictions
- **Weekly Predictions**: Automated predictions for upcoming games

### Content Generation
- **AI-Powered Tweets**: Automatically generate engaging game summaries
- **Multi-Format Posts**: Game recaps, player spotlights, goalie highlights
- **Twitter Integration**: Post directly to Twitter/X

## Getting Started

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Setup database (PostgreSQL required)
python src/database/setup_db.py
```

### Configuration

Edit `config.py` with your API keys:
- `ANTHROPIC_API_KEY`: Claude AI API key
- `TWITTER_API_KEY`, `TWITTER_API_SECRET`, etc.: Twitter API credentials

### Usage

```bash
# Run main pipeline (fetch latest game, generate tweets, post)
python scripts/pipeline.py

# Run home/away analysis
python src/analytics/home_away_analysis.py

# Train prediction model (coming soon)
python scripts/train_model.py
```

## Data Sources

- **PWHL API**: `https://lscluster.hockeytech.com/feed/`
- **Database**: PostgreSQL (local)

## Project Status

**Current Features:**
- ✅ Automated game data fetching
- ✅ Database storage and querying
- ✅ Statistical analysis (home/away, career stats, attendance)
- ✅ AI-powered content generation
- ✅ Twitter posting automation
- 🚧 Prediction models (in development)

**Next Steps:**
- Build feature engineering pipeline
- Train baseline prediction model
- Implement weekly prediction workflow
- Add prediction results to Twitter posts

## Contributing

This is a personal learning project for analytics and machine learning.

## License

Personal project - not licensed for redistribution.
