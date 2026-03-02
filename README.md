PWHL Automated Anlaytic post creation
- Pull weekly stats
- Determine star player of the week, and pull current standings
- create social media post outlining highlights
- push to google drice for posting and alert Dev via twillio to post

- DB hosted via railway.app
- Automation handled by github actions

GitHub Actions (weekly_recap.yml)
│
├── 1. checkout repo
├── 2. pip install dependencies  
├── 3. python run_weekly.py
│       │
│       ├── subprocess → update.py
│       │       ├── db_config.py      ← reads PWHL_DATABASE_URL from env
│       │       ├── backfill.py       ← fetch_schedule(), load_game()
│       │       └── models.py         ← SQLAlchemy table definitions
│       │
│       ├── render_weekly_recap.py
│       │       ├── db_queries.py     ← reads PWHL_DATABASE_URL from env
│       │       └── templates/*.html
│       │
│       └── drive_upload.py           ← reads GOOGLE_* from env
│
└── 4. upload-artifact (output/*.png)
