#!/usr/bin/env python3
"""
Top 10 Players Visualization
Creates professional graphics for career and season leaders
Uses official PWHL API for accurate stats
"""

import sys
import os
from datetime import datetime

# Add to path
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
sys.path.insert(0, parent_dir)

from fetch_career_stats import fetch_career_stats, fetch_season_stats
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from PIL import Image
import numpy as np

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


def load_team_logo(team_code, size=(50, 50)):
    """
    Load team logo image

    Args:
        team_code: Team code (e.g., 'BOS', 'MTL')
        size: Tuple of (width, height) for logo

    Returns:
        PIL Image object or None if not found
    """
    logo_path = os.path.join(parent_dir, 'assets', 'logos', f'{team_code}_50x50.png')

    try:
        img = Image.open(logo_path)
        if img.size != size:
            img = img.resize(size, Image.Resampling.LANCZOS)
        return img
    except Exception as e:
        print(f"⚠️  Could not load logo for {team_code}: {e}")
        return None


def create_top_players_viz(stat='points', limit=10, season_id=None, output_file=None):
    """
    Create top players visualization

    Args:
        stat: Stat to visualize ('points', 'goals', 'assists')
        limit: Number of players to show
        season_id: Optional season filter (use 'all' for career)
        output_file: Output filename
    """
    # Get data from official PWHL API
    if season_id == 'all' or season_id is None:
        print("Fetching career stats from PWHL API...")
        leaders = fetch_career_stats('skater', limit)
    else:
        print(f"Fetching season {season_id} stats from PWHL API...")
        leaders = fetch_season_stats('skater', limit, int(season_id))

    if not leaders:
        print("❌ No data found")
        return None

    # Set up figure
    fig, ax = plt.subplots(figsize=(12, limit * 0.6 + 2))
    ax.axis('off')

    # Title
    season_text = f"Season {season_id}" if season_id else "All-Time Career"
    title_text = f"PWHL {season_text} Leaders - {stat.upper()}"
    subtitle_text = f"Updated: {datetime.now().strftime('%B %d, %Y')}"

    ax.text(0.5, 0.98, title_text, ha='center', va='top',
            fontsize=22, fontweight='bold', transform=ax.transAxes)
    ax.text(0.5, 0.94, subtitle_text, ha='center', va='top',
            fontsize=11, color='gray', transform=ax.transAxes)

    # Table parameters
    row_height = 0.065
    start_y = 0.88

    # Column positions (adjusted for logo)
    cols = {
        'rank': 0.06,
        'logo': 0.14,  # Team logo
        'name': 0.22,
        'pos': 0.50,
        'gp': 0.60,
        'g': 0.70,
        'a': 0.80,
        'pts': 0.90,
        'ppg': 0.98
    }

    # Header
    header_y = start_y
    headers = {
        'rank': 'RK',
        'name': 'PLAYER',
        'pos': 'POS',
        'gp': 'GP',
        'g': 'G',
        'a': 'A',
        'pts': 'PTS',
        'ppg': 'PPG'
    }

    for col, label in headers.items():
        ha = 'left' if col == 'name' else 'center'
        ax.text(cols[col], header_y, label, ha=ha, va='center',
                fontsize=12, fontweight='bold', transform=ax.transAxes)

    # Header underline
    ax.plot([0.02, 1.0], [header_y - 0.02, header_y - 0.02],
            'k-', linewidth=2, transform=ax.transAxes)

    # Draw each player row
    for idx, player in enumerate(leaders):
        y_pos = start_y - (idx + 1) * row_height

        # Alternating background
        if idx % 2 == 0:
            rect = patches.Rectangle((0.02, y_pos - row_height/2 + 0.005),
                                     0.98, row_height * 0.9,
                                     linewidth=0, edgecolor='none',
                                     facecolor='#f5f5f5',
                                     transform=ax.transAxes, zorder=0)
            ax.add_patch(rect)

        # Rank with color gradient
        rank = idx + 1
        if rank == 1:
            rank_color = '#FFD700'  # Gold
        elif rank == 2:
            rank_color = '#C0C0C0'  # Silver
        elif rank == 3:
            rank_color = '#CD7F32'  # Bronze
        else:
            rank_color = '#333333'

        ax.text(cols['rank'], y_pos, str(rank), ha='center', va='center',
                fontsize=16, fontweight='bold', color=rank_color,
                transform=ax.transAxes)

        # Team logo
        team_code = player.get('team_code', '')
        if team_code:
            logo = load_team_logo(team_code)
            if logo:
                imagebox = OffsetImage(logo, zoom=0.35)
                ab = AnnotationBbox(imagebox, (cols['logo'], y_pos),
                                   frameon=False, xycoords='axes fraction')
                ax.add_artist(ab)

        # Player name (bold)
        name = player.get('name', '')
        ax.text(cols['name'], y_pos, name, ha='left', va='center',
                fontsize=12, fontweight='bold', transform=ax.transAxes)

        # Position (API uses 'position_str' not 'position')
        position = player.get('position_str', player.get('position', 'F'))
        ax.text(cols['pos'], y_pos, position, ha='center', va='center',
                fontsize=11, transform=ax.transAxes)

        # Stats
        gp = int(player.get('games_played', 0))
        goals = int(player.get('goals', 0))
        assists = int(player.get('assists', 0))
        points = int(player.get('points', 0))

        ax.text(cols['gp'], y_pos, str(gp), ha='center', va='center',
                fontsize=11, transform=ax.transAxes)
        ax.text(cols['g'], y_pos, str(goals), ha='center', va='center',
                fontsize=11, transform=ax.transAxes)
        ax.text(cols['a'], y_pos, str(assists), ha='center', va='center',
                fontsize=11, transform=ax.transAxes)

        # Highlighted stat
        ax.text(cols['pts'], y_pos, str(points), ha='center', va='center',
                fontsize=13, fontweight='bold', color='#C8102E',
                transform=ax.transAxes)

        # Points per game (calculate it)
        ppg = points / gp if gp > 0 else 0
        ax.text(cols['ppg'], y_pos, f"{ppg:.2f}", ha='center', va='center',
                fontsize=11, transform=ax.transAxes)

    # Visual bar chart for top stat
    bar_start_y = start_y - (limit + 0.5) * row_height
    bar_width = 0.88
    bar_x = 0.06

    # Get max value for scaling
    max_val = max([p[stat] for p in leaders])

    for idx, player in enumerate(leaders):
        y_pos = bar_start_y - idx * 0.03
        val = player[stat]
        bar_length = (val / max_val) * bar_width

        # Draw bar
        bar_color = '#C8102E' if idx == 0 else '#69B3E7'
        rect = patches.Rectangle((bar_x, y_pos - 0.008),
                                 bar_length, 0.016,
                                 linewidth=0, edgecolor='none',
                                 facecolor=bar_color, alpha=0.7,
                                 transform=ax.transAxes, zorder=1)
        ax.add_patch(rect)

    plt.tight_layout()

    # Output filename
    if not output_file:
        season_suffix = f"_season_{season_id}" if season_id else "_career"
        output_file = f"top_players_{stat}{season_suffix}.png"

    plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"✅ Visualization saved to: {output_file}")

    return output_file


def create_top_goalies_viz(limit=10, season_id=None, output_file=None):
    """Create top goalies visualization"""
    # Get data from official PWHL API
    if season_id == 'all' or season_id is None:
        print("Fetching career goalie stats from PWHL API...")
        leaders = fetch_career_stats('goalie', limit)
    else:
        print(f"Fetching season {season_id} goalie stats from PWHL API...")
        leaders = fetch_season_stats('goalie', limit, int(season_id))

    if not leaders:
        print("❌ No goalie data found")
        return None

    # Set up figure
    fig, ax = plt.subplots(figsize=(12, limit * 0.6 + 2))
    ax.axis('off')

    # Title
    season_text = f"Season {season_id}" if season_id else "All-Time Career"
    title_text = f"PWHL {season_text} Goalie Leaders - SAVE PERCENTAGE"
    subtitle_text = f"Updated: {datetime.now().strftime('%B %d, %Y')}"

    ax.text(0.5, 0.98, title_text, ha='center', va='top',
            fontsize=22, fontweight='bold', transform=ax.transAxes)
    ax.text(0.5, 0.94, subtitle_text, ha='center', va='top',
            fontsize=11, color='gray', transform=ax.transAxes)

    # Table parameters
    row_height = 0.065
    start_y = 0.88

    # Column positions (adjusted for logo)
    cols = {
        'rank': 0.06,
        'logo': 0.14,  # Team logo
        'name': 0.22,
        'gp': 0.52,
        'sa': 0.62,
        'sv': 0.72,
        'svpct': 0.82,
        'gaa': 0.92,
        'so': 0.98
    }

    # Header
    header_y = start_y
    headers = {
        'rank': 'RK',
        'name': 'GOALIE',
        'gp': 'GP',
        'sa': 'SA',
        'sv': 'SV',
        'svpct': 'SV%',
        'gaa': 'GAA',
        'so': 'SO'
    }

    for col, label in headers.items():
        ha = 'left' if col == 'name' else 'center'
        ax.text(cols[col], header_y, label, ha=ha, va='center',
                fontsize=12, fontweight='bold', transform=ax.transAxes)

    ax.plot([0.02, 1.0], [header_y - 0.02, header_y - 0.02],
            'k-', linewidth=2, transform=ax.transAxes)

    # Draw each goalie row
    for idx, goalie in enumerate(leaders):
        y_pos = start_y - (idx + 1) * row_height

        if idx % 2 == 0:
            rect = patches.Rectangle((0.02, y_pos - row_height/2 + 0.005),
                                     0.98, row_height * 0.9,
                                     linewidth=0, edgecolor='none',
                                     facecolor='#f5f5f5',
                                     transform=ax.transAxes, zorder=0)
            ax.add_patch(rect)

        # Rank
        rank = idx + 1
        rank_color = '#FFD700' if rank == 1 else '#C0C0C0' if rank == 2 else '#CD7F32' if rank == 3 else '#333333'

        ax.text(cols['rank'], y_pos, str(rank), ha='center', va='center',
                fontsize=16, fontweight='bold', color=rank_color,
                transform=ax.transAxes)

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
                fontsize=12, fontweight='bold', transform=ax.transAxes)

        # Stats
        gp = int(goalie.get('games_played', 0))
        sa = int(goalie.get('shots_against', 0))
        sv = int(goalie.get('saves', 0))
        svpct = float(goalie.get('save_percentage', 0))
        gaa = float(goalie.get('goals_against_average', 0))
        shutouts = int(goalie.get('shutouts', 0))

        ax.text(cols['gp'], y_pos, str(gp), ha='center', va='center',
                fontsize=11, transform=ax.transAxes)
        ax.text(cols['sa'], y_pos, str(sa), ha='center', va='center',
                fontsize=11, transform=ax.transAxes)
        ax.text(cols['sv'], y_pos, str(sv), ha='center', va='center',
                fontsize=11, transform=ax.transAxes)

        # Highlighted SV%
        ax.text(cols['svpct'], y_pos, f"{svpct:.3f}", ha='center', va='center',
                fontsize=13, fontweight='bold', color='#C8102E',
                transform=ax.transAxes)

        ax.text(cols['gaa'], y_pos, f"{gaa:.2f}", ha='center', va='center',
                fontsize=11, transform=ax.transAxes)
        ax.text(cols['so'], y_pos, str(shutouts), ha='center', va='center',
                fontsize=11, transform=ax.transAxes)

    plt.tight_layout()

    if not output_file:
        season_suffix = f"_season_{season_id}" if season_id else "_career"
        output_file = f"top_goalies{season_suffix}.png"

    plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"✅ Visualization saved to: {output_file}")

    return output_file


def main():
    """Main function"""
    print("=" * 60)
    print("TOP PLAYERS VISUALIZATION")
    print("=" * 60)

    import argparse
    parser = argparse.ArgumentParser(description='Create top players visualizations')
    parser.add_argument('--stat', choices=['points', 'goals', 'assists'], default='points',
                       help='Stat to visualize')
    parser.add_argument('--season', type=int, help='Season ID (default: career)')
    parser.add_argument('--limit', type=int, default=10, help='Number of players')
    parser.add_argument('--goalies', action='store_true', help='Show goalies instead')

    args = parser.parse_args()

    if args.goalies:
        print(f"\n🥅 Creating top {args.limit} goalies visualization...")
        create_top_goalies_viz(args.limit, args.season)
    else:
        print(f"\n🏒 Creating top {args.limit} {args.stat} leaders visualization...")
        create_top_players_viz(args.stat, args.limit, args.season)

    print("\n✅ Complete!")


if __name__ == "__main__":
    main()
