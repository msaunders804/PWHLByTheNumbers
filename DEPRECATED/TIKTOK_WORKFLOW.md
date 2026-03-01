# TikTok Posting Workflow

Quick reference guide for posting PWHL visualizations to TikTok

## Quick Start (Once Google Drive is configured)

### On Your Computer

```bash
# Generate standings visualization
python src/visualizers/standings_viz.py

# Generate player leaders
python src/visualizers/skater_leaders_viz.py

# Generate goalie leaders
python src/visualizers/goalie_leaders_viz.py

# Generate TOI leaders
python src/visualizers/toi_leaders_viz.py

# Generate weekly lineup
python src/visualizers/weekly_lineup_viz.py

# Generate attendance viz
python src/visualizers/top_attendance_viz.py
```

Each script will:
1. Create the visualization
2. Save it locally to `outputs/visualizations/`
3. Automatically upload to Google Drive
4. Print a link you can open on your phone

### On Your Phone

1. Open Google Drive app
2. Go to "PWHL Visualizations" folder
3. Tap the latest image
4. Tap share → TikTok
5. Add voiceover/commentary
6. Post!

## Available Visualizations

| Script | What it shows | Best for TikTok |
|--------|---------------|-----------------|
| `standings_viz.py` | Team standings with OTW column | Weekly updates, playoff race |
| `skater_leaders_viz.py` | Top scorers (goals, assists, points) | Player highlights |
| `goalie_leaders_viz.py` | Top goalies (wins, GAA, save %) | Goalie battles |
| `toi_leaders_viz.py` | Ice time leaders | Ironwoman stats |
| `weekly_lineup_viz.py` | Game schedule for the week | Week preview |
| `top_attendance_viz.py` | Highest attendance games | Arena atmosphere |

## Content Ideas for TikTok

### Standings Updates
- "PWHL Standings Update!"
- Discuss playoff race
- Highlight team streaks
- Compare points between teams

### Player Leaders
- "Who's leading the PWHL in scoring?"
- Break down top 5 players
- Compare goals vs assists
- Highlight rookies in top 10

### Weekly Lineup
- "This week in the PWHL..."
- Preview matchups
- Call out rivalry games
- Predict upsets

### Attendance
- "Sold out PWHL game!"
- Talk about fan energy
- Compare venues
- Growth of the league

## Pro Tips

### Timing
- Post standings on Monday mornings (weekend recap)
- Post weekly lineup on Fridays (weekend preview)
- Post player leaders after milestone games
- Post attendance after sellout games

### Engagement
- Ask questions in captions ("Who's your pick for MVP?")
- Use trending sounds
- Add text overlays to highlight key stats
- Respond to comments

### Hashtags
Always include:
- #PWHL
- #WomensHockey
- #HockeyTikTok
- Specific team hashtags (e.g., #PWHLBoston, #PWHLMinnesota)

### Voiceover Ideas
- Explain what makes a stat interesting
- Tell a story about the numbers
- Compare to previous seasons
- Predict what's coming next

## Troubleshooting

### "File not in Google Drive"
- Check that `GOOGLE_DRIVE_ENABLED = True` in config.py
- Make sure you ran the visualizer script
- Wait 5-10 seconds for sync

### "Can't find the visualization"
- Refresh Google Drive app (pull down)
- Check folder name matches config
- Verify you're signed into correct Google account

### "Need to post from computer"
If Google Drive isn't working:
```bash
# Files are always saved locally at:
outputs/visualizations/

# Email to yourself:
# (Set up email notifications - see pipeline.py)
```

## Advanced: Batch Generate All Vizs

Create a script to generate all visualizations at once:

```bash
# Create generate_all.sh
python src/visualizers/standings_viz.py
python src/visualizers/skater_leaders_viz.py
python src/visualizers/goalie_leaders_viz.py
python src/visualizers/toi_leaders_viz.py
python src/visualizers/weekly_lineup_viz.py
```

Then run:
```bash
bash generate_all.sh
```

All visualizations upload to Google Drive, pick which one to post!

## Scheduling Posts

Consider a weekly schedule:
- **Monday**: Standings update (weekend recap)
- **Tuesday**: Player of the week highlight
- **Wednesday**: Goalie leaders
- **Thursday**: Fun stat (attendance, TOI, etc.)
- **Friday**: Weekly lineup preview
- **Saturday/Sunday**: Game day content, live reactions

## Track Performance

Keep notes on what works:
- Which viz types get most views?
- What voiceover style resonates?
- Best posting times?
- Which hashtags drive traffic?

Use this data to refine your content strategy!
