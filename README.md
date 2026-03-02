# BTN Automation Pipeline

## Overview

Every Monday at 9AM CST, GitHub Actions automatically generates and delivers the PWHL weekly recap slides.

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
        │         └── reads GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,
        │               GOOGLE_REFRESH_TOKEN, GOOGLE_DRIVE_FOLDER_ID
        │               from GitHub Secrets
        │
        └─── Step 4: GitHub Actions Artifact Upload
             └── output/*.png saved as artifacts (7 day retention)
```

---

## File Reference

| File | Purpose |
|------|---------|
| `.github/workflows/weekly_recap.yml` | Defines the GitHub Actions schedule and job steps |
| `run_weekly.py` | Master script — chains all 4 steps |
| `update.py` | Incremental DB update — fetches only new games since last run |
| `backfill.py` | Full season load — used for initial setup only |
| `db_config.py` | Database connection — reads from `.env` locally, GitHub Secrets in CI |
| `db_queries.py` | All query logic — standings, scores, story of week, slide 1 player |
| `models.py` | SQLAlchemy ORM table definitions |
| `render_weekly_recap.py` | Renders all 4 slides via Jinja2 + Playwright |
| `drive_upload.py` | Uploads rendered PNGs to Google Drive via OAuth |
| `notify.py` | SMS/MMS alerts via Twilio |

---

## Credentials

All secrets are stored in GitHub → Settings → Secrets and variables → Actions.
Never committed to the repo.

| Secret | Used By | Description |
|--------|---------|-------------|
| `PWHL_DATABASE_URL` | `db_config.py` | Railway MySQL connection string |
| `GOOGLE_CLIENT_ID` | `drive_upload.py` | OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | `drive_upload.py` | OAuth client secret |
| `GOOGLE_REFRESH_TOKEN` | `drive_upload.py` | OAuth refresh token |
| `GOOGLE_DRIVE_FOLDER_ID` | `drive_upload.py` | Target Drive folder ID |

---

## Local Development

```powershell
# Run full pipeline (uses .env for credentials)
python run_weekly.py

# Skip Drive upload (faster for testing renders)
python run_weekly.py --skip-drive --skip-sms

# Update DB only
python update.py

# Dry run — see what games would be loaded without writing
python update.py --dry-run

# Render with sample data
python render_weekly_recap.py --sample
```

---

## Schedule

Runs automatically every **Monday at 9:00 AM CST**.

To change the schedule, edit the cron value in `.github/workflows/weekly_recap.yml`:
```yaml
- cron: '0 14 * * 1'   # 14:00 UTC = 9AM CST
```

To trigger manually: GitHub repo → **Actions** → **PWHL Weekly Recap** → **Run workflow**
