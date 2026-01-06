#!/usr/bin/env python3
"""
PWHL Goalie Save Percentage Leaders Visualization
Creates professional graphics for top goalie stats
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


def fetch_goalie_leaders(season_id=8, limit=10):
    """
    Fetch top goalie save percentage leaders from official PWHL API

    Args:
        season_id: Season ID (default: 8)
        limit: Number of goalies to return

    Returns:
        List of goalie dictionaries sorted by save percentage
    """
    params = {
        'feed': 'statviewfeed',
        'view': 'players',
        'season': season_id,
        'team': 'all',
        'position': 'goalies',
        'rookies': 0,
        'statsType': 'standard',
        'rosterstatus': 'undefined',
        'site_id': 0,
        'first': 0,
        'limit': 500,
        'sort': 'save_percentage',
        'league_id': 1,
        'lang': 'en',
        'division': -1,
        'conference': -1,
        'qualified': 'all',
        'key': API_KEY,
        'client_code': CLIENT_CODE
    }

    try:
        print(f"Fetching goalie leaders from PWHL API (Season {season_id})...")
        response = requests.get(API_BASE_URL, params=params, timeout=10)
        response.raise_for_status()

        # This API returns JSONP format, need to strip the wrapper
        text = response.text
        if text.startswith('([') and text.endswith('])'):
            text = text[1:-1]  # Remove outer ()

        import json
        data = json.loads(text)

        # Extract goalies from the data structure
        if isinstance(data, list) and len(data) > 0:
            sections = data[0].get('sections', [])
            if sections and len(sections) > 0:
                goalies_data = sections[0].get('data', [])
                goalies = [g['row'] for g in goalies_data if 'row' in g]
            else:
                goalies = []
        else:
            goalies = []

        # Filter for minimum games played (at least 1 game)
        qualified_goalies = [
            g for g in goalies
            if int(g.get('games_played', 0)) >= 1
        ]

        # Already sorted by save_percentage from API, just take top N
        top_goalies = qualified_goalies[:limit]

        print(f"Retrieved {len(top_goalies)} goalies")
        return top_goalies

    except Exception as e:
        print(f"Error fetching goalie leaders: {e}")
        import traceback
        traceback.print_exc()
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


def create_goalie_leaders_viz(season_id=8, limit=10, output_file=None):
    """
    Create goalie save percentage leaders visualization

    Args:
        season_id: Season ID (default: 8)
        limit: Number of goalies to show
        output_file: Output filename (optional)

    Returns:
        Path to saved file or None
    """
    # Fetch data
    goalies = fetch_goalie_leaders(season_id, limit)

    if not goalies:
        print("No goalie data available")
        return None

    # Set up figure for Instagram (1080x1080 square format)
    fig, ax = plt.subplots(figsize=(10.8, 10.8), facecolor='white')
    ax.set_facecolor('white')
    ax.axis('off')

    # Title with BTN style
    title_text = "PWHL GOALIE LEADERS"
    subtitle_text = f"Season {season_id} • Save Percentage • Updated: {datetime.now().strftime('%B %d, %Y')}"

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
        'gp': 0.52,
        'w': 0.62,
        'sa': 0.72,
        'sv': 0.82,
        'svpct': 0.92,
        'gaa': 0.99
    }

    # Header
    header_y = start_y
    headers = {
        'rank': 'RK',
        'name': 'GOALIE',
        'gp': 'GP',
        'w': 'W',
        'sa': 'SA',
        'sv': 'SV',
        'svpct': 'SV%',
        'gaa': 'GAA'
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

    # Draw each goalie row
    for idx, goalie in enumerate(goalies):
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
        team_code = goalie.get('team_code', '')
        if team_code:
            logo = load_team_logo(team_code)
            if logo:
                imagebox = OffsetImage(logo, zoom=0.35)
                ab = AnnotationBbox(imagebox, (cols['logo'], y_pos),
                                   frameon=False, xycoords='axes fraction')
                ax.add_artist(ab)

        # Goalie name
        name = goalie.get('name', '')
        ax.text(cols['name'], y_pos, name, ha='left', va='center',
                fontsize=11, fontweight='black', family='sans-serif',
                transform=ax.transAxes)

        # Stats
        gp = int(goalie.get('games_played', 0))
        wins = int(goalie.get('wins', 0))
        shots = int(goalie.get('shots', 0))
        saves = int(goalie.get('saves', 0))
        svpct = float(goalie.get('save_percentage', 0))
        gaa = float(goalie.get('goals_against_average', 0))

        ax.text(cols['gp'], y_pos, str(gp), ha='center', va='center',
                fontsize=11, transform=ax.transAxes)
        ax.text(cols['w'], y_pos, str(wins), ha='center', va='center',
                fontsize=11, transform=ax.transAxes)
        ax.text(cols['sa'], y_pos, str(shots), ha='center', va='center',
                fontsize=11, transform=ax.transAxes)
        ax.text(cols['sv'], y_pos, str(saves), ha='center', va='center',
                fontsize=11, transform=ax.transAxes)

        # Highlighted save percentage
        ax.text(cols['svpct'], y_pos, f"{svpct:.3f}", ha='center', va='center',
                fontsize=14, fontweight='black', color=BTN_PURPLE,
                family='sans-serif', transform=ax.transAxes)

        ax.text(cols['gaa'], y_pos, f"{gaa:.2f}", ha='center', va='center',
                fontsize=10, transform=ax.transAxes)

    # Add minimum games note
    note_y = 0.05
    ax.text(0.5, note_y, "Minimum 1 game played", ha='center', va='bottom',
            fontsize=8, color='#666', style='italic', transform=ax.transAxes)

    # Adjust layout to minimize whitespace
    plt.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)

    # Output filename
    if not output_file:
        timestamp = datetime.now().strftime('%Y%m%d')
        output_dir = os.path.join(parent_dir, 'outputs', 'visualizations')
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, f'pwhl_goalie_leaders_{timestamp}.png')

    # Save at 100 DPI for exact 1080x1080 Instagram format
    plt.savefig(output_file, dpi=100, bbox_inches=None, facecolor='white', pad_inches=0)
    print(f"Visualization saved to: {output_file}")

    plt.close()
    return output_file


def main():
    """Main function"""
    print("=" * 70)
    print("PWHL GOALIE SAVE PERCENTAGE LEADERS VISUALIZATION")
    print("=" * 70)

    import argparse
    parser = argparse.ArgumentParser(description='Create PWHL goalie leaders visualization')
    parser.add_argument('--season', type=int, default=8,
                       help='Season ID (default: 8)')
    parser.add_argument('--limit', type=int, default=10,
                       help='Number of goalies (default: 10)')
    parser.add_argument('--output', type=str, help='Output file path')

    args = parser.parse_args()

    print(f"\nCreating goalie leaders visualization for season {args.season}...")
    output_file = create_goalie_leaders_viz(args.season, args.limit, args.output)

    if output_file:
        print("\nComplete!")
        print(f"File saved: {output_file}")
    else:
        print("\nFailed to create visualization")


if __name__ == "__main__":
    main()
