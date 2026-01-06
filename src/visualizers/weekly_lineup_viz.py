#!/usr/bin/env python3
"""
PWHL Weekly Lineup Visualization
Creates Instagram-optimized graphic showing upcoming week's games
Matches BTN Weekly Lineup style with purple accents
"""

import os
import sys
from datetime import datetime, timedelta
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from PIL import Image

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.database.fetch_data import fetch_season_schedule

# BTN Brand Colors
BTN_PURPLE = '#6B4DB8'
BTN_PURPLE_LIGHT = '#9B7DD4'

# PWHL team colors
TEAM_COLORS = {
    'BOS': '#154734',
    'MIN': '#2C5234',
    'MTL': '#862633',
    'NY': '#69B3E7',
    'OTT': '#C8102E',
    'TOR': '#00B2A9',
    'SEA': '#001628',
    'VAN': '#9A7E3D',
}


def load_team_logo(team_code, size=(120, 120)):
    """Load team logo image"""
    parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    possible_paths = [
        os.path.join(parent_dir, 'assets', 'logos', f'{team_code}_50x50.png'),
        os.path.join(parent_dir, 'assets', 'logos', f'{team_code}.png'),
        os.path.join(parent_dir, 'src', 'assets', 'logos', f'{team_code}_50x50.png'),
    ]

    for logo_path in possible_paths:
        try:
            img = Image.open(logo_path)
            if img.size != size:
                img = img.resize(size, Image.Resampling.LANCZOS)
            return img
        except Exception:
            continue

    return None


def calculate_game_score(game):
    """
    Calculate a score for game importance/watchability

    Scoring criteria:
    - Weekend game (Sat/Sun): +2 points
    - Primetime (7pm or later): +1 point
    - Rivalry matchup: +2 points
    - Top teams (based on simple heuristic): +1 point each

    Args:
        game: Game dict

    Returns:
        Integer score
    """
    score = 0

    # Weekend bonus
    day_of_week = game['date'].weekday()  # Monday=0, Sunday=6
    if day_of_week in [5, 6]:  # Saturday or Sunday
        score += 2

    # Primetime bonus (7pm EST or later)
    time_str = game.get('time', 'TBD')
    if time_str != 'TBD' and ':' in time_str:
        try:
            hour = int(time_str.split(':')[0])
            if hour >= 19:  # 7pm or later
                score += 1
        except:
            pass

    # Rivalry matchups (traditional rivalries)
    rivalries = [
        {'TOR', 'MTL'},  # Toronto vs Montreal
        {'TOR', 'OTT'},  # Toronto vs Ottawa (Ontario rivalry)
        {'BOS', 'NY'},   # Boston vs New York
        {'MIN', 'BOS'},  # Minnesota vs Boston
    ]

    matchup = {game['home_team'], game['away_team']}
    for rivalry in rivalries:
        if matchup == rivalry:
            score += 2
            break

    # Top teams (MTL, MIN, TOR, BOS typically strong)
    top_teams = {'MTL', 'MIN', 'TOR', 'BOS'}
    if game['home_team'] in top_teams:
        score += 1
    if game['away_team'] in top_teams:
        score += 1

    return score


def get_upcoming_games(days_ahead=7, season_id=8):
    """
    Get upcoming games from API

    Args:
        days_ahead: Number of days to look ahead
        season_id: Season ID

    Returns:
        List of upcoming game dicts
    """
    today = datetime.now().date()
    end_date = today + timedelta(days=days_ahead)

    schedule = fetch_season_schedule(season_id=season_id)
    upcoming = []

    for game in schedule['SiteKit']['Schedule']:
        game_date = datetime.strptime(game['date_played'], '%Y-%m-%d').date()

        # Only include games in our date range that haven't been played yet
        if today <= game_date <= end_date and not game.get('game_status', '').startswith('Final'):
            # Map team IDs to codes
            team_mapping = {
                '1': 'BOS', '2': 'MIN', '3': 'MTL', '4': 'NY',
                '5': 'OTT', '6': 'TOR', '7': 'TBD', '8': 'SEA', '9': 'VAN'
            }

            home_code = team_mapping.get(str(game.get('home_team', '')), '')
            away_code = team_mapping.get(str(game.get('visiting_team', '')), '')

            upcoming.append({
                'game_id': game['id'],
                'date': game_date,
                'time': game.get('schedule_time', 'TBD'),
                'home_team': home_code,
                'away_team': away_code,
                'home_team_name': game.get('home_team_name', 'TBD'),
                'away_team_name': game.get('visiting_team_name', 'TBD'),
                'venue': game.get('venue', 'TBD')
            })

    # Calculate scores for each game
    for game in upcoming:
        game['watch_score'] = calculate_game_score(game)

    # Sort by date and time
    upcoming.sort(key=lambda x: (x['date'], x['time']))

    return upcoming


def create_weekly_lineup_viz(season_id=8, output_file=None):
    """
    Create BTN-style weekly lineup visualization

    Args:
        season_id: Season ID (default: 8)
        output_file: Output filename (optional)

    Returns:
        Path to saved file
    """
    # Get upcoming games
    games = get_upcoming_games(days_ahead=7, season_id=season_id)

    if not games:
        print("No upcoming games found")
        return None

    # Limit to first 6 games to match mockup
    games = games[:6]

    # Find the game to watch (highest score)
    if games:
        game_to_watch_idx = max(range(len(games)), key=lambda i: games[i]['watch_score'])
    else:
        game_to_watch_idx = 0

    # Set up figure for Instagram (1080x1080 square format)
    fig, ax = plt.subplots(figsize=(10.8, 10.8), facecolor='white')
    ax.set_facecolor('white')
    ax.axis('off')

    # Title - BTN WEEKLY LINEUP - even bigger font
    title_text = "BTN WEEKLY LINEUP"
    ax.text(0.5, 0.96, title_text, ha='center', va='top',
            fontsize=50, fontweight='black', family='sans-serif',
            transform=ax.transAxes)

    # Purple underline under title - extended to fully frame title with more spacing
    ax.plot([0.12, 0.88], [0.895, 0.895], color=BTN_PURPLE, linewidth=6,
            transform=ax.transAxes, solid_capstyle='round')

    # Game layout parameters
    game_height = 0.14
    start_y = 0.87

    # Draw each game
    for idx, game in enumerate(games):
        y_pos = start_y - (idx * game_height)

        # Date and time on left - stacked vertically
        # Day of week
        day_str = game['date'].strftime('%a').upper()
        # Date - format without leading zeros
        date_str = f"{game['date'].month}/{game['date'].day}"
        # Time - convert from 24hr format to 12hr with EST (no AM/PM)
        time_raw = game['time']
        if time_raw != 'TBD' and ':' in time_raw:
            try:
                hour, minute, _ = time_raw.split(':')
                hour = int(hour)
                if hour == 0:
                    time_str = '12 EST'
                elif hour < 12:
                    time_str = f'{hour} EST'
                elif hour == 12:
                    time_str = '12 EST'
                else:
                    time_str = f'{hour - 12} EST'
            except:
                time_str = '7 EST'
        else:
            time_str = '7 EST'

        # Stack: Day, Date, Time - shifted more to the right
        ax.text(0.17, y_pos - game_height/2 + 0.025, day_str, ha='left', va='center',
                fontsize=20, fontweight='black', family='sans-serif',
                transform=ax.transAxes)

        ax.text(0.17, y_pos - game_height/2, date_str, ha='left', va='center',
                fontsize=19, fontweight='bold', family='sans-serif',
                transform=ax.transAxes)

        ax.text(0.17, y_pos - game_height/2 - 0.025, time_str, ha='left', va='center',
                fontsize=15, fontweight='bold', family='sans-serif',
                transform=ax.transAxes)

        # Away team logo (left side) - maintaining spacing from date/time
        if game['away_team']:
            away_logo = load_team_logo(game['away_team'])
            if away_logo:
                imagebox = OffsetImage(away_logo, zoom=0.68)
                ab = AnnotationBbox(imagebox, (0.34, y_pos - game_height/2),
                                   frameon=False, xycoords='axes fraction')
                ax.add_artist(ab)

        # Matchup text in center (CITY V CITY format) - shifted right
        # Extract city from team name (e.g., "Montreal Victoire" -> "Montreal", "New York Sirens" -> "New York")
        def get_city_name(team_name):
            if team_name == 'TBD':
                return team_name
            # Special handling for "New York"
            if team_name.startswith('New York'):
                return 'New York'
            # For other teams, take first word
            return team_name.split()[0]

        away_city = get_city_name(game['away_team_name'])
        home_city = get_city_name(game['home_team_name'])

        matchup = f"{away_city.upper()} V {home_city.upper()}"
        ax.text(0.56, y_pos - game_height/2, matchup, ha='center', va='center',
                fontsize=18, fontweight='black', family='sans-serif',
                transform=ax.transAxes)

        # Show "Game to Watch" with stars on the highest-scored game
        if idx == game_to_watch_idx:
            # Create 5-pointed star function
            def create_star(center_x, center_y, outer_r, inner_r):
                angles_outer = np.linspace(0, 2*np.pi, 6) + np.pi/2  # Start at top
                angles_inner = angles_outer + np.pi/5  # Offset for inner points

                vertices = []
                for i in range(5):
                    # Outer point
                    vertices.append([center_x + outer_r * np.cos(angles_outer[i]),
                                   center_y + outer_r * np.sin(angles_outer[i])])
                    # Inner point
                    vertices.append([center_x + inner_r * np.cos(angles_inner[i]),
                                   center_y + inner_r * np.sin(angles_inner[i])])
                return vertices

            # Left star (to the left of date/time) - moved closer to edge
            # Logo size is 120x120 at zoom 0.68 = ~82 pixels
            # Match that size for stars (outer radius ~0.04 in axes fraction)
            left_star_x = 0.115
            left_star_y = y_pos - game_height/2
            left_star_vertices = create_star(left_star_x, left_star_y, 0.035, 0.014)
            left_star = patches.Polygon(left_star_vertices, facecolor=BTN_PURPLE, edgecolor='none',
                                       transform=ax.transAxes, zorder=10)
            ax.add_patch(left_star)

            # Right star (to the right of home team logo) - moved closer to edge
            right_star_x = 0.885
            right_star_y = y_pos - game_height/2
            right_star_vertices = create_star(right_star_x, right_star_y, 0.035, 0.014)
            right_star = patches.Polygon(right_star_vertices, facecolor=BTN_PURPLE, edgecolor='none',
                                        transform=ax.transAxes, zorder=10)
            ax.add_patch(right_star)

            # "Game to Watch" text
            ax.text(0.56, y_pos - game_height/2 - 0.03, "Game to Watch",
                    ha='center', va='center',
                    fontsize=11, color='#666', style='italic',
                    transform=ax.transAxes)

        # Home team logo (right side) - shifted right
        if game['home_team']:
            home_logo = load_team_logo(game['home_team'])
            if home_logo:
                imagebox = OffsetImage(home_logo, zoom=0.68)
                ab = AnnotationBbox(imagebox, (0.78, y_pos - game_height/2),
                                   frameon=False, xycoords='axes fraction')
                ax.add_artist(ab)

        # Purple separator line between games - shorter to match title width
        if idx < len(games) - 1:
            ax.plot([0.12, 0.88], [y_pos - game_height/2 - 0.055, y_pos - game_height/2 - 0.055],
                    color=BTN_PURPLE_LIGHT, linewidth=2,
                    transform=ax.transAxes, solid_capstyle='round')

    # Purple line beneath final game
    final_y = start_y - (len(games) - 1) * game_height - game_height/2 - 0.055
    ax.plot([0.12, 0.88], [final_y, final_y], color=BTN_PURPLE_LIGHT, linewidth=2,
            transform=ax.transAxes, solid_capstyle='round')

    # Adjust layout
    plt.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)

    # Output filename
    if not output_file:
        timestamp = datetime.now().strftime('%Y%m%d')
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                                  'outputs', 'visualizations')
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, f'pwhl_weekly_lineup_{timestamp}.png')

    # Save at 100 DPI for exact 1080x1080 Instagram format
    plt.savefig(output_file, dpi=100, bbox_inches=None, facecolor='white', pad_inches=0)
    print(f"Visualization saved to: {output_file}")

    plt.close()
    return output_file


def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description='Create PWHL weekly lineup visualization')
    parser.add_argument('--season', type=int, default=8,
                       help='Season ID (default: 8)')
    parser.add_argument('--output', type=str, help='Output file path')

    args = parser.parse_args()

    print("=" * 70)
    print("PWHL WEEKLY LINEUP VISUALIZATION")
    print("=" * 70)

    print(f"\nCreating weekly lineup for season {args.season}...")
    output_file = create_weekly_lineup_viz(season_id=args.season, output_file=args.output)

    if output_file:
        print("\nComplete!")
        print(f"File saved: {output_file}")
        return 0
    else:
        print("\nFailed to create visualization")
        return 1


if __name__ == "__main__":
    sys.exit(main())
