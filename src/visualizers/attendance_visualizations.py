#!/usr/bin/env python3
"""
PWHL Attendance Trends Visualization
Creates graphs showing attendance trends for each team
Updated to use PostgreSQL database and BTN purple styling
"""

import os
import sys
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as patches
import numpy as np

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.database.db_queries import Session
from src.database.db_models import Game, Team

# BTN Brand Colors
BTN_PURPLE = '#6B4DB8'
BTN_PURPLE_LIGHT = '#9B7DD4'

# PWHL team colors (matching other visualizations)
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

# Team full names
TEAM_NAMES = {
    'BOS': 'Boston Fleet',
    'MIN': 'Minnesota Frost',
    'MTL': 'Montréal Victoire',
    'NY': 'New York Sirens',
    'OTT': 'Ottawa Charge',
    'TOR': 'Toronto Sceptres',
    'SEA': 'Seattle Torrent',
    'VAN': 'Vancouver Goldeneyes',
}


def load_attendance_data_from_db(season_id=None):
    """
    Load attendance records from database

    Args:
        season_id: Optional season ID to filter (default: all seasons)

    Returns:
        List of game dicts with attendance data
    """
    session = Session()
    try:
        query = session.query(Game, Team).join(
            Team, Game.home_team_id == Team.team_id
        ).filter(
            Game.game_status == 'final',
            Game.attendance.isnot(None)
        )

        if season_id:
            query = query.filter(Game.season_id == season_id)

        results = query.order_by(Game.date).all()

        games = []
        for game, home_team in results:
            # Get away team
            away_team = session.query(Team).filter(Team.team_id == game.away_team_id).first()

            games.append({
                'game_id': game.game_id,
                'date': game.date.strftime('%Y-%m-%d'),
                'home_team': home_team.team_code,
                'home_team_name': home_team.team_name,
                'visitor_team': away_team.team_code if away_team else 'UNK',
                'visitor_team_name': away_team.team_name if away_team else 'Unknown',
                'attendance': game.attendance,
                'venue': game.venue if game.venue else 'Unknown Venue',
                'season_id': game.season_id
            })

        return games
    finally:
        session.close()


def get_season_from_date(date_str):
    """
    Determine which PWHL season a game belongs to

    Args:
        date_str: Date string in YYYY-MM-DD format

    Returns:
        String like "2023-24", "2024-25", "2025-26"
    """
    date = datetime.strptime(date_str, '%Y-%m-%d')
    year = date.year
    month = date.month

    # PWHL season runs roughly January-May
    # If month is Jan-June, season is (year-1)-(year)
    # If month is Jul-Dec, season is (year)-(year+1)

    if month >= 1 and month <= 6:
        season = f"{year-1}-{str(year)[2:]}"
    else:
        season = f"{year}-{str(year+1)[2:]}"

    return season


def create_team_comparison_bar(games, output_file=None):
    """
    Create Instagram-optimized bar chart comparing average attendance by team
    Uses BTN purple styling

    Args:
        games: List of game dicts
        output_file: Where to save (optional)

    Returns:
        Path to saved file
    """

    print("Creating team attendance comparison...")

    # Calculate averages
    team_totals = {}
    team_counts = {}

    for game in games:
        home = game['home_team']
        att = game['attendance']

        if home not in team_totals:
            team_totals[home] = 0
            team_counts[home] = 0

        team_totals[home] += att
        team_counts[home] += 1

    # Calculate averages
    team_averages = {
        team: team_totals[team] / team_counts[team]
        for team in team_totals
    }

    # Sort by average (descending)
    sorted_teams = sorted(team_averages.items(), key=lambda x: x[1], reverse=True)
    teams = [t[0] for t in sorted_teams]
    averages = [t[1] for t in sorted_teams]

    # Get team colors
    bar_colors = [TEAM_COLORS.get(t, '#666666') for t in teams]

    # Create figure for Instagram (1080x1080 square format)
    fig, ax = plt.subplots(figsize=(10.8, 10.8), facecolor='white')
    ax.set_facecolor('white')

    # Title with BTN style
    title_text = "PWHL AVERAGE ATTENDANCE"
    subtitle_text = f"Home Games • Updated: {datetime.now().strftime('%B %d, %Y')}"

    ax.text(0.5, 0.96, title_text, ha='center', va='top',
            fontsize=28, fontweight='black', family='sans-serif',
            transform=ax.transAxes)

    # Purple underline
    ax.plot([0.12, 0.88], [0.93, 0.93], color=BTN_PURPLE, linewidth=4,
            transform=ax.transAxes, solid_capstyle='round')

    ax.text(0.5, 0.90, subtitle_text, ha='center', va='top',
            fontsize=10, color='#333', transform=ax.transAxes)

    # Create bars - position them in the plot area
    bar_positions = np.arange(len(teams))
    bars = ax.bar(bar_positions, averages, color=bar_colors, alpha=0.85,
                  edgecolor='#333', linewidth=1.5)

    # Add value labels on bars
    for i, (bar, avg, team) in enumerate(zip(bars, averages, teams)):
        height = bar.get_height()
        # Value on top of bar
        ax.text(bar.get_x() + bar.get_width()/2., height + 300,
                f'{int(avg):,}',
                ha='center', va='bottom', fontsize=12, fontweight='black')
        # Game count below value
        ax.text(bar.get_x() + bar.get_width()/2., height + 50,
                f'({team_counts[team]} games)',
                ha='center', va='bottom', fontsize=9, color='#666')

    # Set x-axis labels to team codes
    ax.set_xticks(bar_positions)
    ax.set_xticklabels(teams, fontsize=13, fontweight='bold')

    # Format y-axis
    ax.set_ylabel('Average Attendance', fontsize=13, fontweight='bold')
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{int(x):,}'))
    ax.tick_params(axis='y', labelsize=11)

    # Grid
    ax.grid(True, alpha=0.3, linestyle='--', axis='y', zorder=0)
    ax.set_axisbelow(True)

    # Add league average line
    league_avg = np.mean(averages)
    ax.axhline(y=league_avg, color=BTN_PURPLE, linestyle='--',
               linewidth=2.5, alpha=0.8, zorder=3)

    # Label for league average
    ax.text(len(teams) - 0.5, league_avg + 200,
            f'League Avg: {league_avg:,.0f}',
            ha='right', va='bottom', fontsize=11, fontweight='bold',
            color=BTN_PURPLE,
            bbox=dict(boxstyle='round,pad=0.5', facecolor='white',
                     edgecolor=BTN_PURPLE, linewidth=2))

    # Set y-axis limits with some padding
    max_val = max(averages)
    ax.set_ylim(0, max_val * 1.15)

    # Remove top and right spines
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    # Adjust layout
    plt.subplots_adjust(left=0.08, right=0.98, top=0.88, bottom=0.06)

    # Output filename
    if not output_file:
        timestamp = datetime.now().strftime('%Y%m%d')
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                                  'outputs', 'visualizations')
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, f'pwhl_attendance_comparison_{timestamp}.png')

    # Save at 100 DPI for exact 1080x1080 Instagram format
    plt.savefig(output_file, dpi=100, bbox_inches=None, facecolor='white', pad_inches=0)
    print(f"Visualization saved to: {output_file}")

    plt.close()
    return output_file


def create_attendance_trend_viz(games, output_file=None):
    """
    Create Instagram-optimized attendance trend visualization
    Shows trends for top 4 teams by average attendance
    Uses BTN purple styling

    Args:
        games: List of game dicts
        output_file: Where to save (optional)

    Returns:
        Path to saved file
    """

    print("Creating attendance trend visualization...")

    # Calculate team averages to get top 4
    team_data = {}
    for game in games:
        home = game['home_team']
        if home not in team_data:
            team_data[home] = {'games': [], 'total': 0, 'count': 0}

        team_data[home]['games'].append({
            'date': datetime.strptime(game['date'], '%Y-%m-%d'),
            'attendance': game['attendance']
        })
        team_data[home]['total'] += game['attendance']
        team_data[home]['count'] += 1

    # Calculate averages and get top 4
    team_averages = {
        team: data['total'] / data['count']
        for team, data in team_data.items()
    }
    top_teams = sorted(team_averages.items(), key=lambda x: x[1], reverse=True)[:4]
    top_team_codes = [t[0] for t in top_teams]

    # Create figure for Instagram
    fig, ax = plt.subplots(figsize=(10.8, 10.8), facecolor='white')
    ax.set_facecolor('white')

    # Title with BTN style
    title_text = "PWHL ATTENDANCE TRENDS"
    subtitle_text = f"Top 4 Teams • Updated: {datetime.now().strftime('%B %d, %Y')}"

    ax.text(0.5, 0.96, title_text, ha='center', va='top',
            fontsize=28, fontweight='black', family='sans-serif',
            transform=ax.transAxes)

    # Purple underline
    ax.plot([0.12, 0.88], [0.93, 0.93], color=BTN_PURPLE, linewidth=4,
            transform=ax.transAxes, solid_capstyle='round')

    ax.text(0.5, 0.90, subtitle_text, ha='center', va='top',
            fontsize=10, color='#333', transform=ax.transAxes)

    # Plot each team
    for team_code in top_team_codes:
        data = team_data[team_code]
        dates = [g['date'] for g in data['games']]
        attendance = [g['attendance'] for g in data['games']]

        color = TEAM_COLORS.get(team_code, '#666666')
        team_name = TEAM_NAMES.get(team_code, team_code)
        avg = team_averages[team_code]

        ax.plot(dates, attendance, marker='o', linewidth=2.5, markersize=6,
               label=f'{team_name} (Avg: {avg:,.0f})',
               color=color, alpha=0.85)

    # Formatting
    ax.set_xlabel('Date', fontsize=13, fontweight='bold')
    ax.set_ylabel('Attendance', fontsize=13, fontweight='bold')

    # Format y-axis
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{int(x):,}'))
    ax.tick_params(axis='both', labelsize=11)

    # Format x-axis dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')

    # Grid
    ax.grid(True, alpha=0.3, linestyle='--', zorder=0)
    ax.set_axisbelow(True)

    # Legend with BTN purple border
    legend = ax.legend(loc='lower left', fontsize=11, framealpha=0.95,
                      edgecolor=BTN_PURPLE, fancybox=True)
    legend.get_frame().set_linewidth(2)

    # Remove top and right spines
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    # Adjust layout
    plt.subplots_adjust(left=0.10, right=0.98, top=0.88, bottom=0.08)

    # Output filename
    if not output_file:
        timestamp = datetime.now().strftime('%Y%m%d')
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                                  'outputs', 'visualizations')
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, f'pwhl_attendance_trends_{timestamp}.png')

    # Save at 100 DPI for exact 1080x1080 Instagram format
    plt.savefig(output_file, dpi=100, bbox_inches=None, facecolor='white', pad_inches=0)
    print(f"Visualization saved to: {output_file}")

    plt.close()
    return output_file


def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description='Create PWHL attendance visualizations')
    parser.add_argument('--season', type=int, help='Season ID to filter (default: all seasons)')
    parser.add_argument('--type', choices=['comparison', 'trends', 'both'],
                       default='both', help='Type of visualization to create')
    parser.add_argument('--output-dir', type=str, help='Output directory')

    args = parser.parse_args()

    print("=" * 70)
    print("PWHL ATTENDANCE VISUALIZATIONS")
    print("=" * 70)

    # Load data from database
    print("\nLoading attendance data from database...")
    games = load_attendance_data_from_db(season_id=args.season)

    if not games:
        print("No games with attendance data found in database")
        return 1

    print(f"Loaded {len(games)} games with attendance data")

    # Determine season range
    seasons = list(set([get_season_from_date(g['date']) for g in games]))
    print(f"Seasons covered: {', '.join(sorted(seasons))}\n")

    # Create visualizations
    try:
        if args.type in ['comparison', 'both']:
            output_file = None
            if args.output_dir:
                os.makedirs(args.output_dir, exist_ok=True)
                timestamp = datetime.now().strftime('%Y%m%d')
                output_file = os.path.join(args.output_dir,
                                          f'pwhl_attendance_comparison_{timestamp}.png')
            create_team_comparison_bar(games, output_file)
            print()

        if args.type in ['trends', 'both']:
            output_file = None
            if args.output_dir:
                os.makedirs(args.output_dir, exist_ok=True)
                timestamp = datetime.now().strftime('%Y%m%d')
                output_file = os.path.join(args.output_dir,
                                          f'pwhl_attendance_trends_{timestamp}.png')
            create_attendance_trend_viz(games, output_file)
            print()

        print("=" * 70)
        print("VISUALIZATIONS CREATED SUCCESSFULLY!")
        print("=" * 70)
        return 0

    except Exception as e:
        print(f"\nError creating visualizations: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
