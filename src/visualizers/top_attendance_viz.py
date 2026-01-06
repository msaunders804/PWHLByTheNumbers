#!/usr/bin/env python3
"""
PWHL Top Attended Games Visualization
Creates Instagram-optimized graphic showing highest attended games in PWHL history
Uses BTN purple styling
"""

import os
import sys
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.database.db_queries import Session
from src.database.db_models import Game, Team

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


def get_top_attended_games(limit=10, season_id=None):
    """
    Get top attended games from database

    Args:
        limit: Number of games to return (default: 10)
        season_id: Optional season filter

    Returns:
        List of game dicts sorted by attendance (descending)
    """
    session = Session()
    try:
        from sqlalchemy.orm import aliased

        # Create aliases for home and away teams
        HomeTeam = aliased(Team)
        AwayTeam = aliased(Team)

        query = session.query(Game, HomeTeam, AwayTeam).join(
            HomeTeam, Game.home_team_id == HomeTeam.team_id
        ).join(
            AwayTeam, Game.away_team_id == AwayTeam.team_id
        ).filter(
            Game.game_status == 'final',
            Game.attendance.isnot(None)
        )

        if season_id:
            query = query.filter(Game.season_id == season_id)

        # Order by attendance descending
        results = query.order_by(Game.attendance.desc()).limit(limit).all()

        games = []
        for game, home_team, away_team in results:
            games.append({
                'game_id': game.game_id,
                'date': game.date.strftime('%Y-%m-%d'),
                'home_team': home_team.team_code,
                'home_team_name': home_team.team_name,
                'away_team': away_team.team_code,
                'away_team_name': away_team.team_name,
                'attendance': game.attendance,
                'venue': game.venue if game.venue else 'Unknown',
                'home_score': game.home_score,
                'away_score': game.away_score,
                'season_id': game.season_id
            })

        return games
    finally:
        session.close()


def create_top_attendance_viz(limit=10, season_id=None, highlight_game_id=None, output_file=None):
    """
    Create Instagram-optimized top attended games visualization

    Args:
        limit: Number of games to show (default: 10)
        season_id: Optional season filter
        highlight_game_id: Optional game ID to highlight
        output_file: Output filename (optional)

    Returns:
        Path to saved file
    """
    # Fetch data
    games = get_top_attended_games(limit=limit, season_id=season_id)

    if not games:
        print("No games with attendance data found")
        return None

    # Set up figure for Instagram (1080x1080 square format)
    fig, ax = plt.subplots(figsize=(10.8, 10.8), facecolor='white')
    ax.set_facecolor('white')
    ax.axis('off')

    # Title with BTN style
    if season_id:
        title_text = f"PWHL SEASON {season_id} TOP ATTENDANCE"
    else:
        title_text = "PWHL ALL-TIME TOP ATTENDANCE"

    subtitle_text = f"Top {len(games)} Games • Updated: {datetime.now().strftime('%B %d, %Y')}"

    ax.text(0.5, 0.96, title_text, ha='center', va='top',
            fontsize=26, fontweight='black', family='sans-serif',
            transform=ax.transAxes)

    # Purple underline
    ax.plot([0.12, 0.88], [0.93, 0.93], color=BTN_PURPLE, linewidth=4,
            transform=ax.transAxes, solid_capstyle='round')

    ax.text(0.5, 0.90, subtitle_text, ha='center', va='top',
            fontsize=10, color='#333', transform=ax.transAxes)

    # Table parameters
    row_height = 0.072
    start_y = 0.84

    # Column positions
    cols = {
        'rank': 0.04,
        'date': 0.12,
        'matchup': 0.26,
        'venue': 0.58,
        'attendance': 0.92
    }

    # Header
    header_y = start_y
    headers = {
        'rank': 'RK',
        'date': 'DATE',
        'matchup': 'MATCHUP',
        'venue': 'VENUE',
        'attendance': 'ATT'
    }

    for col, label in headers.items():
        ha = 'left' if col in ['matchup', 'venue'] else 'center'
        ax.text(cols[col], header_y, label, ha=ha, va='center',
                fontsize=12, fontweight='black', family='sans-serif',
                transform=ax.transAxes)

    # Purple header underline
    ax.plot([0.01, 0.99], [header_y - 0.015, header_y - 0.015],
            color=BTN_PURPLE, linewidth=3, transform=ax.transAxes,
            solid_capstyle='round')

    # Draw each game row
    for idx, game in enumerate(games):
        y_pos = start_y - (idx + 1) * row_height

        # Check if this is the highlighted game
        is_highlighted = highlight_game_id and game['game_id'] == highlight_game_id

        # Alternating background with special highlight
        if is_highlighted:
            # Gold/yellow highlight for the specified game
            rect = patches.Rectangle((0.01, y_pos - row_height/2 + 0.004),
                                     0.98, row_height * 0.92,
                                     linewidth=2, edgecolor=BTN_PURPLE,
                                     facecolor='#FFF9E6',
                                     transform=ax.transAxes, zorder=0)
            ax.add_patch(rect)
        elif idx < 3:
            # Light purple tint for top 3
            rect = patches.Rectangle((0.01, y_pos - row_height/2 + 0.004),
                                     0.98, row_height * 0.92,
                                     linewidth=0, edgecolor='none',
                                     facecolor='#f3f0f9' if idx % 2 == 0 else '#faf8fd',
                                     transform=ax.transAxes, zorder=0)
            ax.add_patch(rect)
        elif idx % 2 == 0:
            rect = patches.Rectangle((0.01, y_pos - row_height/2 + 0.004),
                                     0.98, row_height * 0.92,
                                     linewidth=0, edgecolor='none',
                                     facecolor='#f5f5f5',
                                     transform=ax.transAxes, zorder=0)
            ax.add_patch(rect)

        # Rank
        rank = idx + 1
        rank_color = BTN_PURPLE if rank <= 3 or is_highlighted else '#666666'
        rank_weight = 'black' if rank <= 3 or is_highlighted else 'bold'

        ax.text(cols['rank'], y_pos, str(rank), ha='center', va='center',
                fontsize=14, fontweight=rank_weight, color=rank_color,
                family='sans-serif', transform=ax.transAxes)

        # Date
        date_str = datetime.strptime(game['date'], '%Y-%m-%d').strftime('%m/%d/%y')
        ax.text(cols['date'], y_pos, date_str, ha='center', va='center',
                fontsize=10, transform=ax.transAxes)

        # Matchup with score
        matchup = f"{game['away_team']} @ {game['home_team']} ({game['away_score']}-{game['home_score']})"
        matchup_color = BTN_PURPLE if is_highlighted else '#000000'
        matchup_weight = 'black' if is_highlighted else 'bold'

        ax.text(cols['matchup'], y_pos, matchup, ha='left', va='center',
                fontsize=10, fontweight=matchup_weight, color=matchup_color,
                family='sans-serif', transform=ax.transAxes)

        # Venue (shortened)
        venue = game['venue']
        if '|' in venue:
            venue_name = venue.split('|')[0].strip()
        else:
            venue_name = venue

        # Truncate long venue names
        if len(venue_name) > 25:
            venue_name = venue_name[:22] + '...'

        ax.text(cols['venue'], y_pos, venue_name, ha='left', va='center',
                fontsize=9, color='#666', transform=ax.transAxes)

        # Attendance (highlighted)
        att_color = BTN_PURPLE if is_highlighted else BTN_PURPLE
        att_weight = 'black'
        att_size = 13 if is_highlighted else 12

        ax.text(cols['attendance'], y_pos, f"{game['attendance']:,}", ha='center', va='center',
                fontsize=att_size, fontweight=att_weight, color=att_color,
                family='sans-serif', transform=ax.transAxes)

    # Add note if a game is highlighted
    if highlight_game_id:
        note_y = 0.04
        highlight_game = next((g for g in games if g['game_id'] == highlight_game_id), None)
        if highlight_game:
            rank = games.index(highlight_game) + 1
            note_text = f"Game {highlight_game_id} ranks #{rank} all-time"
            ax.text(0.5, note_y, note_text, ha='center', va='bottom',
                    fontsize=11, color=BTN_PURPLE, fontweight='black',
                    style='italic', transform=ax.transAxes)

    # Adjust layout to minimize whitespace
    plt.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)

    # Output filename
    if not output_file:
        timestamp = datetime.now().strftime('%Y%m%d')
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                                  'outputs', 'visualizations')
        os.makedirs(output_dir, exist_ok=True)

        if season_id:
            output_file = os.path.join(output_dir, f'pwhl_top_attendance_season{season_id}_{timestamp}.png')
        else:
            output_file = os.path.join(output_dir, f'pwhl_top_attendance_alltime_{timestamp}.png')

    # Save at 100 DPI for exact 1080x1080 Instagram format
    plt.savefig(output_file, dpi=100, bbox_inches=None, facecolor='white', pad_inches=0)
    print(f"Visualization saved to: {output_file}")

    plt.close()
    return output_file


def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description='Create PWHL top attendance visualization')
    parser.add_argument('--limit', type=int, default=10,
                       help='Number of games to show (default: 10)')
    parser.add_argument('--season', type=int,
                       help='Season ID to filter (default: all seasons)')
    parser.add_argument('--highlight', type=int,
                       help='Game ID to highlight in the list')
    parser.add_argument('--output', type=str, help='Output file path')

    args = parser.parse_args()

    print("=" * 70)
    print("PWHL TOP ATTENDED GAMES VISUALIZATION")
    print("=" * 70)

    print(f"\nCreating top {args.limit} attendance visualization...")
    if args.season:
        print(f"Season filter: {args.season}")
    if args.highlight:
        print(f"Highlighting game: {args.highlight}")

    output_file = create_top_attendance_viz(
        limit=args.limit,
        season_id=args.season,
        highlight_game_id=args.highlight,
        output_file=args.output
    )

    if output_file:
        print("\nComplete!")
        print(f"File saved: {output_file}")
    else:
        print("\nFailed to create visualization")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
