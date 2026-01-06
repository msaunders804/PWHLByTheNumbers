#!/usr/bin/env python3
"""
PWHL Team Standings Visualization
Creates professional graphics for current team standings
Uses official PWHL API with 3-2-1-0 point system
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

# PWHL API Configuration
API_BASE_URL = "https://lscluster.hockeytech.com/feed/index.php"
API_KEY = "446521baf8c38984"
CLIENT_CODE = "pwhl"


def fetch_standings(season_id=8):
    """
    Fetch current PWHL standings from official API

    Args:
        season_id: Season ID (default: 8 for current season)

    Returns:
        List of team standings dictionaries
    """
    params = {
        'feed': 'modulekit',
        'view': 'statviewtype',
        'stat': 'conference',
        'type': 'standings',
        'season_id': season_id,
        'key': API_KEY,
        'client_code': CLIENT_CODE
    }

    try:
        print(f"Fetching standings from PWHL API (Season {season_id})...")
        response = requests.get(API_BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Extract standings data
        standings = data.get('SiteKit', {}).get('Statviewtype', [])

        # Filter out header rows
        team_standings = [team for team in standings if isinstance(team, dict) and 'team_id' in team]

        print(f"Retrieved standings for {len(team_standings)} teams")
        return team_standings

    except Exception as e:
        print(f"Error fetching standings: {e}")
        return []


def load_team_logo(team_code, size=(50, 50)):
    """
    Load team logo image

    Args:
        team_code: Team code (e.g., 'BOS', 'MTL')
        size: Tuple of (width, height) for logo

    Returns:
        PIL Image object or None if not found
    """
    # Try multiple possible locations
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

    print(f"Warning: Could not load logo for {team_code}")
    return None


def create_standings_viz(season_id=8, output_file=None):
    """
    Create PWHL standings visualization

    Args:
        season_id: Season ID (default: 8)
        output_file: Output filename (optional)

    Returns:
        Path to saved file or None
    """
    # Fetch data
    standings = fetch_standings(season_id)

    if not standings:
        print("No standings data available")
        return None

    # Sort by points (already sorted by API, but ensure it)
    standings = sorted(standings, key=lambda x: int(x.get('points', 0)), reverse=True)

    # Set up figure for Instagram (1080x1080 square format)
    # Using 10.8x10.8 inches at 100 DPI = 1080x1080 pixels
    num_teams = len(standings)
    fig, ax = plt.subplots(figsize=(10.8, 10.8), facecolor='white')
    ax.set_facecolor('white')
    ax.axis('off')

    # BTN Brand Colors - Purple accent
    BTN_PURPLE = '#6B4DB8'  # Main purple accent
    BTN_PURPLE_LIGHT = '#9B7DD4'  # Light purple for accents

    # Title with BTN style - bold black text (optimized spacing for Instagram)
    title_text = "PWHL STANDINGS"
    subtitle_text = f"Season {season_id} • Updated: {datetime.now().strftime('%B %d, %Y')}"

    ax.text(0.5, 0.96, title_text, ha='center', va='top',
            fontsize=28, fontweight='black', family='sans-serif',
            transform=ax.transAxes)

    # Purple underline under title (like BTN template)
    ax.plot([0.12, 0.88], [0.93, 0.93], color=BTN_PURPLE, linewidth=4,
            transform=ax.transAxes, solid_capstyle='round')

    ax.text(0.5, 0.90, subtitle_text, ha='center', va='top',
            fontsize=10, color='#333', transform=ax.transAxes)

    # Add 3-2-1-0 explanation
    points_explanation = "3pts (Reg Win) • 2pts (OT/SO Win) • 1pt (OT/SO Loss) • 0pts (Reg Loss)"
    ax.text(0.5, 0.87, points_explanation, ha='center', va='top',
            fontsize=8, color='#555', style='italic', transform=ax.transAxes)

    # Table parameters - optimized for 8 teams in square format
    row_height = 0.072
    start_y = 0.82

    # Column positions - removed GF/GA, spread out remaining columns
    cols = {
        'rank': 0.06,
        'logo': 0.14,
        'team': 0.26,
        'gp': 0.50,
        'w': 0.59,
        'otw': 0.68,
        'l': 0.77,
        'otl': 0.86,
        'pts': 0.95,
    }

    # Header with BTN style - bold and using purple accent
    header_y = start_y
    headers = {
        'rank': 'RK',
        'team': 'TEAM',
        'gp': 'GP',
        'w': 'W',
        'otw': 'OTW',
        'l': 'L',
        'otl': 'OTL',
        'pts': 'PTS',
    }

    for col, label in headers.items():
        ha = 'left' if col == 'team' else 'center'
        ax.text(cols[col], header_y, label, ha=ha, va='center',
                fontsize=16, fontweight='black', family='sans-serif',
                transform=ax.transAxes)

    # Purple header underline (BTN style)
    ax.plot([0.01, 0.99], [header_y - 0.015, header_y - 0.015],
            color=BTN_PURPLE, linewidth=3, transform=ax.transAxes,
            solid_capstyle='round')

    # Determine playoff cutoff based on number of teams
    # Season 5-7: 6 teams, top 4 make playoffs
    # Season 8+: 8 teams, top 6 make playoffs
    num_teams = len(standings)
    playoff_spots = 6 if num_teams >= 8 else 4
    playoff_line_y = start_y - (playoff_spots + 0.5) * row_height

    # Draw each team row
    for idx, team in enumerate(standings):
        y_pos = start_y - (idx + 1) * row_height

        # Highlight playoff teams
        is_playoff_team = idx < playoff_spots

        # Alternating background with playoff highlight using purple tint
        if is_playoff_team:
            # Light purple tint for playoff teams (BTN style)
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

        # Rank with playoff indicator
        rank = idx + 1
        clinched = team.get('clinched', '')
        rank_text = f"{clinched}{rank}" if clinched else str(rank)

        # Color code rank - use purple for playoff teams (BTN style)
        if rank <= playoff_spots:
            rank_color = BTN_PURPLE  # Purple for playoff teams
            rank_weight = 'black'
        else:
            rank_color = '#666666'
            rank_weight = 'bold'

        ax.text(cols['rank'], y_pos, rank_text, ha='center', va='center',
                fontsize=14, fontweight=rank_weight, color=rank_color,
                family='sans-serif', transform=ax.transAxes)

        # Team logo
        team_code = team.get('team_code', '')
        if team_code:
            logo = load_team_logo(team_code)
            if logo:
                imagebox = OffsetImage(logo, zoom=0.4)
                ab = AnnotationBbox(imagebox, (cols['logo'], y_pos),
                                   frameon=False, xycoords='axes fraction')
                ax.add_artist(ab)

        # Team name - bolder font like BTN template
        team_name = team.get('name', '')
        ax.text(cols['team'], y_pos, team_name, ha='left', va='center',
                fontsize=15, fontweight='black', family='sans-serif',
                transform=ax.transAxes)

        # Stats
        gp = team.get('games_played', '0')
        wins = team.get('wins', '0')
        otw = team.get('ot_wins', '0')
        losses = team.get('losses', '0')
        otl = team.get('ot_losses', '0')
        points = team.get('points', '0')

        # Display stats with larger fonts
        ax.text(cols['gp'], y_pos, str(gp), ha='center', va='center',
                fontsize=15, fontweight='bold', transform=ax.transAxes)
        ax.text(cols['w'], y_pos, str(wins), ha='center', va='center',
                fontsize=15, fontweight='bold', transform=ax.transAxes)
        ax.text(cols['otw'], y_pos, str(otw), ha='center', va='center',
                fontsize=15, fontweight='bold', transform=ax.transAxes)
        ax.text(cols['l'], y_pos, str(losses), ha='center', va='center',
                fontsize=15, fontweight='bold', transform=ax.transAxes)
        ax.text(cols['otl'], y_pos, str(otl), ha='center', va='center',
                fontsize=15, fontweight='bold', transform=ax.transAxes)

        # Highlighted points - use purple accent
        ax.text(cols['pts'], y_pos, str(points), ha='center', va='center',
                fontsize=18, fontweight='black', color=BTN_PURPLE,
                family='sans-serif', transform=ax.transAxes)

    # Draw playoff line with purple (BTN style)
    ax.plot([0.01, 0.99], [playoff_line_y, playoff_line_y],
            color=BTN_PURPLE_LIGHT, linestyle='--', linewidth=2.5, alpha=0.7,
            transform=ax.transAxes)
    ax.text(0.99, playoff_line_y + 0.01, 'Playoff Line', ha='right', va='bottom',
            fontsize=9, color=BTN_PURPLE, fontweight='black', style='italic',
            family='sans-serif', transform=ax.transAxes)

    # Add legend for clinch indicators - positioned higher to reduce bottom whitespace
    legend_y = 0.05
    ax.text(0.5, legend_y, "x = Clinched Playoff Spot", ha='center', va='bottom',
            fontsize=8, color='#666', transform=ax.transAxes)

    # Adjust layout to minimize whitespace
    plt.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)

    # Output filename
    if not output_file:
        timestamp = datetime.now().strftime('%Y%m%d')
        output_dir = os.path.join(parent_dir, 'outputs', 'visualizations')
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, f'pwhl_standings_{timestamp}.png')

    # Save at 100 DPI for exact 1080x1080 Instagram format
    plt.savefig(output_file, dpi=100, bbox_inches=None, facecolor='white', pad_inches=0)
    print(f"Visualization saved to: {output_file}")

    plt.close()
    return output_file


def main():
    """Main function"""
    print("=" * 70)
    print("PWHL TEAM STANDINGS VISUALIZATION")
    print("=" * 70)

    import argparse
    parser = argparse.ArgumentParser(description='Create PWHL standings visualization')
    parser.add_argument('--season', type=int, default=8,
                       help='Season ID (default: 8)')
    parser.add_argument('--output', type=str, help='Output file path')

    args = parser.parse_args()

    print(f"\nCreating standings visualization for season {args.season}...")
    output_file = create_standings_viz(args.season, args.output)

    if output_file:
        print("\nComplete!")
        print(f"File saved: {output_file}")
    else:
        print("\nFailed to create visualization")


if __name__ == "__main__":
    main()
