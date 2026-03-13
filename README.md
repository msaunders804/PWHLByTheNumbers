# ByTheNumbers — PWHL Analytics Platform

Public-facing analytics and social media platform for the Professional Women's Hockey League. Built to provide the same depth of data coverage routinely applied to men's leagues.

---

## The Problem

The PWHL, founded in 2024, has no publicly available predictive analytics infrastructure. This project builds that foundation — automated standings analysis, player performance tracking, and Monte Carlo playoff probability modeling — delivered weekly to a public audience via Instagram.

---

## Predictive Model

Playoff probability is estimated via **Monte Carlo simulation** (10,000 iterations per run). Each game's outcome is simulated by drawing goals independently from a **Poisson distribution**, where each team's expected goals (λ) is scaled from their relative strength and the PWHL league average of 2.8 GPG.

**Team strength** is a weighted composite of five features:

| Feature | Description |
|---------|-------------|
| Points % | Blended season + last-10-game recency weighting, PDO-adjusted |
| Rank score | `(streak × 3) + (PPG × 20) + (last5_GD × 1.5)` |
| Home win % | Home ice performance |
| Shots ratio | Possession proxy |
| xG proxy | Shots ratio adjusted for SV% differential vs league average |

Weights were derived via **Ridge Regression** trained on Season 7 team statistics at the 67% season snapshot, with final season points as the target variable. Ridge regularization was applied given the small sample size (n=6 teams).

**Validation against Season 7 final standings:**

| Snapshot | Spearman ρ | p-value |
|----------|-----------|---------|
| 33% | 0.143 | 0.787 |
| 50% | 0.771 | 0.072 |
| **67%** | **0.886** | **0.019** |
| 80% | 0.943 | 0.005 |
| 90% | 0.943 | 0.005 |

Reliable predictive signal emerges after ~67% of games played. At 80%+ the model correctly ranks all six teams. Applied to Season 8 at the 67% snapshot: ρ = 0.976 (p = 0.000).

---

## Data Infrastructure

Game data is sourced from the PWHL HockeyTech API and persisted in a **Railway-hosted MySQL database** via a SQLAlchemy ORM pipeline. GitHub Actions triggers weekly DB updates and content generation automatically.

```
PWHLByTheNumbers/
└── src/pwhl_btn/
    ├── analytics/          Monte Carlo simulation, Ridge regression weight derivation
    ├── db/                 SQLAlchemy models, queries, DB config
    ├── ingest/             Incremental game updates, schedule backfill
    ├── integrations/       Google Drive upload, OAuth
    ├── jobs/               Weekly pipeline orchestration
    ├── render/             Jinja2 + Playwright slide renderers
    │   └── templates/      HTML slide templates (Instagram 1080×1920)
    ├── visualizations/     Poster/presentation charts
    └── output/             Rendered PNGs
```

---

## Weekly Pipelines

Four pipelines run automatically via GitHub Actions and deliver Instagram-ready slides to Google Drive.

| Pipeline | Day | Content |
|----------|-----|---------|
| Weekly Recap | Monday 9AM CST | Scores, standings, story of the week |
| Player Spotlight | Wednesday 9AM CST | Rotating player stat card with AI-generated blurb |
| Power Rankings | Thursday 9AM CST | GF/GA scatter, rank formula, hot player highlight |
| Weekly Preview | Sunday 9AM CST | Upcoming schedule, game to watch, standings |

**Power Rankings formula:** `(streak × 3) + (PPG × 20) + (last5_GD × 1.5)`

**Player Spotlight rotation:** Players cycle through the `featured_players` table to avoid repeats. Top-10 scorers are excluded to surface depth players.

**Game to Watch:** Selected by a composite of standings gap, head-to-head history, and player storylines. Why-watch copy generated via Claude API.

---

## Repository Structure

### Analytics (`src/pwhl_btn/analytics/`)

| File | Purpose |
|------|---------|
| `monte_carlo.py` | Poisson simulation → playoff %, Walter Cup %, projected points |
| `derive_weights.py` | Ridge regression on S7 data → `weights.json` |

### Data Layer (`src/pwhl_btn/db/`)

| File | Purpose |
|------|---------|
| `models.py` | SQLAlchemy ORM: Game, Player, Team, GoalieGameStats, PlayerGameStats |
| `db_queries.py` | All read queries used by renderers and analytics |
| `db_config.py` | DB connection — `.env` locally, GitHub Secrets in CI |

### Ingest (`src/pwhl_btn/ingest/`)

| File | Purpose |
|------|---------|
| `update.py` | Incremental update — upserts newly completed games |
| `backfill_schedule.py` | Seeds full season schedule (unplayed rows) |

### Renderers (`src/pwhl_btn/render/`)

| File | Slides | Day |
|------|--------|-----|
| `weekly_recap.py` | 4 — hook, scores, standings, story | Monday |
| `player_spotlight.py` | 1 — player stat card | Wednesday |
| `power_rankings.py` | 3 — hook, scatter, hot player | Thursday |
| `weekly_preview.py` | 4 — hook, schedule, game to watch, standings | Sunday |

### Jobs (`src/pwhl_btn/jobs/`)

| File | Purpose |
|------|---------|
| `run_weekly.py` | Chains DB update → render → Drive upload |
| `sync_toi.py` | Recalculates average TOI per player from API |
| `backfill.py` | Full historical season load (setup only) |

---

## Credentials

Stored in GitHub → Settings → Secrets. Never committed.

| Secret | Used By |
|--------|---------|
| `PWHL_DATABASE_URL` | `db_config.py` — Railway MySQL connection |
| `ANTHROPIC_API_KEY` | `power_rankings.py`, `player_spotlight.py` |
| `GOOGLE_CLIENT_ID` | `google_drive.py` |
| `GOOGLE_CLIENT_SECRET` | `google_drive.py` |
| `GOOGLE_REFRESH_TOKEN` | `google_drive.py` |
| `GOOGLE_DRIVE_FOLDER_ID` | `google_drive.py` |

---

## Local Development

```powershell
# Run from src/pwhl_btn/

# Full recap pipeline
python jobs/run_weekly.py

# Skip uploads for faster render testing
python jobs/run_weekly.py --skip-drive

# Individual renderers
python render/weekly_recap.py
python render/weekly_preview.py
python render/power_rankings.py
python render/player_spotlight.py

# DB update only
python ingest/update.py

# Derive regression weights from Season 7
python analytics/derive_weights.py --game-pct 0.67 --save

# Run Monte Carlo validation
python analytics/monte_carlo.py --season 5 --game-pct 0.67
python analytics/monte_carlo.py --season 8

# Generate accuracy curve chart
python visualizations/plot_accuracy_curve.py
```

To trigger any pipeline manually: GitHub → **Actions** → select workflow → **Run workflow**