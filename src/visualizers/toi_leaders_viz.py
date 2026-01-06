#!/usr/bin/env python3
"""
PWHL Time On Ice Leaders Visualization
Creates professional graphics for TOI leaders
Uses official PWHL API - Instagram optimized format
"""

import sys
import os
from datetime import datetime
import requests
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from PIL import Image

# Add to path
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(script_dir))
sys.path.insert(0, parent_dir)

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

# BTN Brand Colors
BTN_PURPLE = '#6B4DB8'
BTN_PURPLE_LIGHT = '#9B7DD4'

# PWHL API Configuration
API_BASE_URL = "https://lscluster.hockeytech.com/feed/index.php"
API_KEY = "446521baf8c38984"
CLIENT_CODE = "pwhl"


def fetch_toi_leaders(season_id=8, limit=10):
    """
    Fetch time on ice leaders from official PWHL API

    Args:
        season_id: Season ID (default: 8)
        limit: Number of players to return

    Returns:
        List of player dictionaries sorted by average TOI
    """
    params = {
        'feed': 'modulekit',
        'view': 'statviewtype',
        'type': 'topscorers',
        'season_id': season_id,
        'key': API_KEY,
        'client_code': CLIENT_CODE,
        'league_id': 1,
        'first': 0,
        'limit': 50  # Get more then sort
    }

    try:
        print(f"Fetching TOI leaders from PWHL API (Season {season_id})...")
        response = requests.get(API_BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        players = data.get('SiteKit', {}).get('Statviewtype', [])

        # Filter for players with games played and sort by average TOI
        qualified_players = [
            p for p in players
            if int(p.get('games_played', 0)) >= 1
        ]

        # Sort by ice_time_avg (descending) - this is in seconds
        qualified_players.sort(key=lambda x: float(x.get('ice_time_avg', 0)), reverse=True)

        # Take top N
        top_players = qualified_players[:limit]

        print(f"Retrieved {len(top_players)} players")
        return top_players

    except Exception as e:
        print(f"Error fetching TOI leaders: {e}")
        return []


def load_team_logo(team_code, size=(50, 50)):
    """Load team logo image"""
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


def create_toi_leaders_viz(season_id=8, limit=10, output_file=None):
    """
    Create time on ice leaders visualization

    Args:
        season_id: Season ID (default: 8)
        limit: Number of players to show
        output_file: Output filename (optional)

    Returns:
        Path to saved file or None
    """
    # Fetch data
    players = fetch_toi_leaders(season_id, limit)

    if not players:
        print("No TOI data available")
        return None

    # Set up figure for Instagram (1080x1080 square format)
    fig, ax = plt.subplots(figsize=(10.8, 10.8), facecolor='white')
    ax.set_facecolor('white')
    ax.axis('off')

    # Title with BTN style
    title_text = "PWHL TIME ON ICE LEADERS"
    subtitle_text = f"Season {season_id} • Average TOI/Game • Updated: {datetime.now().strftime('%B %d, %Y')}"

    ax.text(0.5, 0.96, title_text, ha='center', va='top',
            fontsize=28, fontweight='black', family='sans-serif',
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
        'logo': 0.10,
        'name': 0.18,
        'pos': 0.50,
        'gp': 0.60,
        'toi_avg': 0.72,
        'toi_total': 0.85,
        'pts': 0.98
    }

    # Header
    header_y = start_y
    headers = {
        'rank': 'RK',
        'name': 'PLAYER',
        'pos': 'POS',
        'gp': 'GP',
        'toi_avg': 'TOI/G',
        'toi_total': 'TOI',
        'pts': 'PTS'
    }

    for col, label in headers.items():
        ha = 'left' if col == 'name' else 'center'
        ax.text(cols[col], header_y, label, ha=ha, va='center',
                fontsize=13, fontweight='black', family='sans-serif',
                transform=ax.transAxes)

    # Purple header underline
    ax.plot([0.01, 0.99], [header_y - 0.015, header_y - 0.015],
            color=BTN_PURPLE, linewidth=3, transform=ax.transAxes,
            solid_capstyle='round')

    # Draw each player row
    for idx, player in enumerate(players):
        y_pos = start_y - (idx + 1) * row_height

        # Alternating background with purple tint for top 3
        if idx < 3:
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
        rank_color = BTN_PURPLE if rank <= 3 else '#666666'
        rank_weight = 'black' if rank <= 3 else 'bold'

        ax.text(cols['rank'], y_pos, str(rank), ha='center', va='center',
                fontsize=14, fontweight=rank_weight, color=rank_color,
                family='sans-serif', transform=ax.transAxes)

        # Team logo
        team_code = player.get('team_code', '')
        if team_code:
            logo = load_team_logo(team_code)
            if logo:
                imagebox = OffsetImage(logo, zoom=0.35)
                ab = AnnotationBbox(imagebox, (cols['logo'], y_pos),
                                   frameon=False, xycoords='axes fraction')
                ax.add_artist(ab)

        # Player name
        name = player.get('name', '')
        ax.text(cols['name'], y_pos, name, ha='left', va='center',
                fontsize=11, fontweight='black', family='sans-serif',
                transform=ax.transAxes)

        # Position
        position = player.get('position', 'F')
        ax.text(cols['pos'], y_pos, position, ha='center', va='center',
                fontsize=11, transform=ax.transAxes)

        # Stats
        gp = int(player.get('games_played', 0))
        points = int(player.get('points', 0))

        # TOI per game (already formatted as MM:SS)
        toi_per_game = player.get('ice_time_per_game_avg', '0:00')

        # Total TOI (already formatted as MM:SS)
        toi_total = player.get('ice_time_minutes_seconds', '0:00')

        ax.text(cols['gp'], y_pos, str(gp), ha='center', va='center',
                fontsize=11, transform=ax.transAxes)

        # Highlighted TOI per game
        ax.text(cols['toi_avg'], y_pos, toi_per_game, ha='center', va='center',
                fontsize=14, fontweight='black', color=BTN_PURPLE,
                family='sans-serif', transform=ax.transAxes)

        ax.text(cols['toi_total'], y_pos, toi_total, ha='center', va='center',
                fontsize=10, transform=ax.transAxes)

        ax.text(cols['pts'], y_pos, str(points), ha='center', va='center',
                fontsize=11, transform=ax.transAxes)

    # Adjust layout to minimize whitespace
    plt.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)

    # Output filename
    if not output_file:
        timestamp = datetime.now().strftime('%Y%m%d')
        output_dir = os.path.join(parent_dir, 'outputs', 'visualizations')
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, f'pwhl_toi_leaders_{timestamp}.png')

    # Save at 100 DPI for exact 1080x1080 Instagram format
    plt.savefig(output_file, dpi=100, bbox_inches=None, facecolor='white', pad_inches=0)
    print(f"Visualization saved to: {output_file}")

    plt.close()
    return output_file


def main():
    """Main function"""
    print("=" * 70)
    print("PWHL TIME ON ICE LEADERS VISUALIZATION")
    print("=" * 70)

    import argparse
    parser = argparse.ArgumentParser(description='Create PWHL TOI leaders visualization')
    parser.add_argument('--season', type=int, default=8,
                       help='Season ID (default: 8)')
    parser.add_argument('--limit', type=int, default=10,
                       help='Number of players (default: 10)')
    parser.add_argument('--output', type=str, help='Output file path')

    args = parser.parse_args()

    print(f"\nCreating TOI leaders visualization for season {args.season}...")
    output_file = create_toi_leaders_viz(args.season, args.limit, args.output)

    if output_file:
        print("\nComplete!")
        print(f"File saved: {output_file}")
    else:
        print("\nFailed to create visualization")


if __name__ == "__main__":
    main()
