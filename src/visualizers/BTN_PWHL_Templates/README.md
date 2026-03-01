# BTN PWHL Templates
ByTheNumbers — Automated PWHL social media graphics

## Project Structure
```
BTN_PWHL_Templates/
├── templates/
│   ├── weekly_preview.html      # Weekly schedule card (light + dark)
│   ├── recap_slide0.html        # Hook slide: BTN Week in Review (always dark)
│   ├── recap_slide1.html        # Recap: scores (light + dark)
│   ├── recap_slide2.html        # Recap: standings (light + dark)
│   └── recap_slide3.html        # Recap: story of the week (always dark/hype)
├── assets/
│   └── logos/                   # Drop team PNG logos here
│       boston.png, minnesota.png, montreal.png, newyork.png
│       ottawa.png, seattle.png, toronto.png, vancouver.png
├── output/                      # Rendered PNGs saved here automatically
├── render_weekly_preview.py
├── render_weekly_recap.py
└── README.md
```

## Setup
```bash
pip install jinja2 playwright
python3 -m playwright install chromium
```

Optional — set DB connection:
```bash
export PWHL_DATABASE_URL=postgresql://localhost/pwhl
```

## Weekly Preview
```bash
python3 render_weekly_preview.py                    # light theme, sample data
python3 render_weekly_preview.py --theme dark       # dark theme (A/B test)
python3 render_weekly_preview.py --from-db          # pull from pipeline
python3 render_weekly_preview.py --output path.png  # custom output path
```

## Weekly Recap (4 slides)
```bash
python3 render_weekly_recap.py                      # light, sample data
python3 render_weekly_recap.py --theme dark         # dark versions
python3 render_weekly_recap.py --from-db            # pull from pipeline
python3 render_weekly_recap.py --override-event     # manually input story of the week
python3 render_weekly_recap.py --out-dir /path/     # custom output folder
```

## Monday Batch (cron)
```bash
# Runs every Monday at 8am — generates all graphics for the week
0 8 * * 1 cd /path/to/BTN_PWHL_Templates && \
  python3 render_weekly_preview.py --from-db && \
  python3 render_weekly_recap.py --from-db
```

## Adding Photos (Story of the Week)
```python
# Local file
event["player_photo"] = "file:///absolute/path/to/photo.jpg"

# Public URL
event["player_photo"] = "https://example.com/action_shot.jpg"
```

## Wiring to Your DB
Both renderers have a get_db_data() function with placeholder SQL.
Update column names to match your schema and set PWHL_DATABASE_URL.

Teaser stats on the hook slide are auto-computed from games/standings data —
no extra queries needed once the base data is wired up.

## Theme Notes
- weekly_preview + recap slides 1 & 2: light by default, --theme dark available
- recap_slide0 (hook): always dark — intentional, sets the tone
- recap_slide3 (story/hype card): always dark — photo-driven, theme flag ignored
