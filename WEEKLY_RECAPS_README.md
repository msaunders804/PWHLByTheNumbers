# PWHL Weekly Recap Visualizations

Four Instagram-optimized visualizations for weekly PWHL recaps, featuring BTN purple branding.

## Created Visualizations

### 1. Team Standings
**Script:** `src/visualizers/standings_viz.py`

Shows current PWHL team standings with:
- All 8 teams (Season 8)
- W-L-OTL records, points, goals for/against, goal differential
- Purple highlight for top 6 playoff teams
- Playoff cutoff line clearly marked
- 3-2-1-0 point system explanation

**Usage:**
```bash
python src/visualizers/standings_viz.py
python src/visualizers/standings_viz.py --season 8 --output custom_path.png
```

### 2. Skater Points Leaders
**Script:** `src/visualizers/skater_leaders_viz.py`

Top point scorers with:
- Default: Top 10 players
- Stats: GP, G, A, PTS, PPG
- Purple highlight for top 3
- Sorted by total points

**Usage:**
```bash
python src/visualizers/skater_leaders_viz.py
python src/visualizers/skater_leaders_viz.py --season 8 --limit 15
```

### 3. Goalie Save Percentage Leaders
**Script:** `src/visualizers/goalie_leaders_viz.py`

Top goalies ranked by save percentage:
- Stats: GP, W, SA, SV, SV%, GAA
- Purple highlight for top 3
- Minimum 1 game played filter
- Filters out "Empty Net" and "Totals" entries

**Usage:**
```bash
python src/visualizers/goalie_leaders_viz.py
python src/visualizers/goalie_leaders_viz.py --season 8 --limit 10
```

**Note:** Early in Season 8, only 2 goalies have appeared in games (Aerin Frankel, Abbey Levy).

### 4. Time On Ice Leaders
**Script:** `src/visualizers/toi_leaders_viz.py`

Top players by average TOI per game:
- Stats: POS, GP, TOI/G, Total TOI, PTS
- Purple highlight for top 3
- Sorted by average TOI per game

**Usage:**
```bash
python src/visualizers/toi_leaders_viz.py
python src/visualizers/toi_leaders_viz.py --season 8 --limit 10
```

## Common Features

All visualizations share:
- ✅ **Instagram Format:** Perfect 1080x1080px square posts
- ✅ **BTN Purple Branding:** Consistent purple accents (#6B4DB8)
- ✅ **Bold Typography:** Heavy fonts matching BTN template style
- ✅ **Team Logos:** Integrated where available
- ✅ **Clean Layout:** Minimal whitespace, optimized spacing
- ✅ **Live API Data:** Fetches current stats from PWHL API
- ✅ **Season 8 Default:** All scripts default to current season

## Output Location

All visualizations save to:
```
outputs/visualizations/
```

With filenames:
- `pwhl_standings_YYYYMMDD.png`
- `pwhl_skater_leaders_YYYYMMDD.png`
- `pwhl_goalie_leaders_YYYYMMDD.png`
- `pwhl_toi_leaders_YYYYMMDD.png`

## Common Command-Line Options

All scripts support:
- `--season N` - Specify season ID (default: 8)
- `--limit N` - Number of entries to show (default: 10)
- `--output PATH` - Custom output file path

## API Information

All visualizations pull live data from the official PWHL API:
- Base URL: `https://lscluster.hockeytech.com/feed/index.php`
- API Key: `446521baf8c38984`
- Client Code: `pwhl`

### API Endpoints Used

1. **Standings:** `type=standings&stat=conference`
2. **Skater Leaders:** `type=topscorers&sort=points`
3. **Goalie Leaders:** `type=goalies` (sorted by save percentage)
4. **TOI Leaders:** `type=topscorers` (sorted by ice_time_avg)

## Design Specifications

### Colors
- **Primary Purple:** `#6B4DB8`
- **Light Purple:** `#9B7DD4`
- **Background:** White
- **Playoff/Top 3 Highlight:** Light purple tint (#f3f0f9, #faf8fd)

### Typography
- **Font Family:** sans-serif
- **Title:** 28pt, black weight
- **Headers:** 13pt, black weight
- **Data:** 11pt regular, with highlights at 14pt black weight

### Layout
- **Image Size:** 10.8 x 10.8 inches
- **DPI:** 100 (produces exactly 1080x1080px)
- **Margins:** 2% on all sides
- **Row Height:** 0.072 (optimized for 8-10 rows)

## Season 8 Teams

The visualizations support all 8 teams:
1. Boston Fleet (BOS)
2. Minnesota Frost (MIN)
3. Montréal Victoire (MTL)
4. New York Sirens (NY)
5. Ottawa Charge (OTT)
6. Toronto Sceptres (TOR)
7. **Seattle Torrent (SEA)** - New expansion team
8. **Vancouver Goldeneyes (VAN)** - New expansion team

## Troubleshooting

### No team logos showing
Logos should be placed in:
- `assets/logos/{TEAM_CODE}_50x50.png`
- `assets/logos/{TEAM_CODE}.png`

### Few goalies showing
Early in the season, few goalies may have played. The filter is set to minimum 1 game played. This is expected and will populate as the season progresses.

### Wrong season data
Ensure you're using `--season 8` or update the default in the scripts.

## Future Enhancements

Potential additions:
- Goal leaders (separate from points)
- Assist leaders
- Plus/minus leaders
- Power play leaders
- Penalty minutes leaders
- Shots on goal leaders
