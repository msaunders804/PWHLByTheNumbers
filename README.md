# BTN Automation Pipeline

## Overview

Three automated pipelines generate and deliver PWHL content to Google Drive on a weekly schedule.

| Pipeline | Schedule | Workflow |
|----------|----------|---------|
| Weekly Recap | Every **Monday** at 9AM CST | `weekly_recap.yml` |
| Weekly Preview | Every **Sunday** at 9AM CST | `weekly_preview.yml` |
| Power Rankings | Every **Thursday** at 9AM CST | `power_rankings.yml` |

---

## Pipeline: Weekly Recap (Monday)

```
GitHub Actions (weekly_recap.yml)
│
├── 1. Checkout repo
├── 2. Install dependencies (pip + playwright)
└── 3. python run_weekly.py
        │
        ├─── Step 1: Update Database
        │    └── update.py
        │         ├── db_config.py       reads PWHL_DATABASE_URL from GitHub Secrets
        │         ├── backfill.py        fetch_schedule(), load_game() from PWHL API
        │         └── models.py          SQLAlchemy table definitions
        │
        ├─── Step 2: Render Slides
        │    └── render_weekly_recap.py
        │         ├── db_queries.py      pulls games, standings, story of week from DB
        │         └── templates/
        │              ├── recap_slide0.html    Hook / Week in Review
        │              ├── recap_slide1.html    Scores
        │              ├── recap_slide2.html    Standings
        │              └── recap_slide3.html    Story of the Week
        │
        ├─── Step 3: Upload to Google Drive
        │    └── drive_upload.py
        │
        └─── Step 4: GitHub Actions Artifact Upload
             └── output/recap_*.png saved as artifacts (7 day retention)
```

---

## Pipeline: Weekly Preview (Sunday)

```
GitHub Actions (weekly_preview.yml)
│
├── 1. Checkout repo
├── 2. Install dependencies (pip + playwright)
└── 3. python render_weekly_preview.py
        │
        ├── db_queries.py      pulls upcoming schedule, standings, game to watch
        └── templates/
             ├── preview_slide0.html    Hook / What's Ahead
             ├── preview_slide1.html    This Week's Games (schedule)
             ├── preview_slide2.html    Game to Watch
             └── preview_slide3.html    Standings
```

---

## Pipeline: Power Rankings (Thursday)

```
GitHub Actions (power_rankings.yml)
│
├── 1. Checkout repo
├── 2. Install dependencies (pip + playwright)
└── 3. python render_power_rankings.py
        │
        ├── db_queries.py      pulls rankings (streak + PPG + last-5 GD),
        │                      offense/defense breakdown, hot player
        ├── Anthropic API      generates opinionated blurbs per team + hot player
        └── templates/
             ├── rankings_slide0.html    Hook (top team, hot/cold streak callouts)
             ├── rankings_slide1.html    Team Identity scatter (GF/pg vs GA/pg)
             └── rankings_slide2.html    Hot Player highlight (photo + last-5 stats)
```

**Rankings formula:** `(streak × 3) + (PPG × 20) + (last5_gd × 1.5)`
Streak is the primary driver — a W5 outweighs any stat advantage.

---

## File Reference

| File | Purpose |
|------|---------|
| `.github/workflows/weekly_recap.yml` | Monday recap schedule and job steps |
| `.github/workflows/weekly_preview.yml` | Sunday preview schedule and job steps |
| `.github/workflows/power_rankings.yml` | Thursday rankings schedule and job steps |
| `run_weekly.py` | Master recap script — chains DB update + render + upload |
| `update.py` | Incremental DB update — fetches only new games since last run |
| `backfill.py` | Full season load — used for initial setup only |
| `db_config.py` | Database connection — reads `.env` locally, GitHub Secrets in CI |
| `db_queries.py` | All query logic — scores, standings, rankings, hot player, schedule |
| `models.py` | SQLAlchemy ORM table definitions |
| `render_weekly_recap.py` | Renders 4 recap slides via Jinja2 + Playwright |
| `render_weekly_preview.py` | Renders 4 preview slides via Jinja2 + Playwright |
| `render_power_rankings.py` | Renders 3 rankings slides via Jinja2 + Playwright |
| `drive_upload.py` | Uploads rendered PNGs to Google Drive via OAuth |
| `notify.py` | SMS/MMS alerts via Twilio |

### Templates

| Template | Pipeline | Content |
|----------|----------|---------|
| `templates/recap_slide0.html` | Recap | Hook / Week in Review |
| `templates/recap_slide1.html` | Recap | Scores |
| `templates/recap_slide2.html` | Recap | Standings |
| `templates/recap_slide3.html` | Recap | Story of the Week |
| `templates/preview_slide0.html` | Preview | Hook / What's Ahead |
| `templates/preview_slide1.html` | Preview | This Week's Games |
| `templates/preview_slide2.html` | Preview | Game to Watch |
| `templates/preview_slide3.html` | Preview | Standings |
| `templates/rankings_slide0.html` | Rankings | Hook |
| `templates/rankings_slide1.html` | Rankings | Team Identity (GF vs GA scatter) |
| `templates/rankings_slide2.html` | Rankings | Hot Player highlight |
| `templates/player_spotlight.html` | Spotlight | Player stat card |
| `templates/goalie_spotlight.html` | Spotlight | Goalie stat card |

### Assets

| Path | Content |
|------|---------|
| `assets/logos/{TEAM}_50x50.png` | Team logos (base64-encoded at render time) |
| `assets/logos/PWHL_logo.svg` | PWHL logo |
| `assets/players/{first}_{last}.jpg` | Candid player photos (checked first) |
| `assets/players/official/{player_id}.jpg` | Official headshots (checked second) |

> Photo resolution order: candid (`first_last.jpg`) → official headshot → leaguestat CDN

---

## Credentials

All secrets are stored in GitHub → Settings → Secrets and variables → Actions.
Never committed to the repo.

| Secret | Used By | Description |
|--------|---------|-------------|
| `PWHL_DATABASE_URL` | `db_config.py` | Railway MySQL connection string |
| `ANTHROPIC_API_KEY` | `render_power_rankings.py` | Claude API for team/player blurbs |
| `GOOGLE_CLIENT_ID` | `drive_upload.py` | OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | `drive_upload.py` | OAuth client secret |
| `GOOGLE_REFRESH_TOKEN` | `drive_upload.py` | OAuth refresh token |
| `GOOGLE_DRIVE_FOLDER_ID` | `drive_upload.py` | Target Drive folder ID |

---

## Local Development

```powershell
# Run full recap pipeline (uses .env for credentials)
python run_weekly.py

# Skip Drive upload (faster for testing renders)
python run_weekly.py --skip-drive --skip-sms

# Render each pipeline with sample data (no DB required)
python render_weekly_recap.py --sample
python render_weekly_preview.py --sample
python render_power_rankings.py --sample

# Update DB only
python update.py

# Dry run — see what games would be loaded without writing
python update.py --dry-run
```

---

## Schedule

| Pipeline | Cron | Workflow file |
|----------|------|---------------|
| Weekly Recap | `0 14 * * 1` — Monday 9AM CST | `weekly_recap.yml` |
| Weekly Preview | `0 14 * * 0` — Sunday 9AM CST | `weekly_preview.yml` |
| Power Rankings | `0 14 * * 4` — Thursday 9AM CST | `power_rankings.yml` |

To trigger any pipeline manually: GitHub repo → **Actions** → select workflow → **Run workflow**
