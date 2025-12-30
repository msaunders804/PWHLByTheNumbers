#!/usr/bin/env python3
"""
PWHL Attendance Trends Visualization
Creates graphs showing attendance trends for each team
"""

import json
import os
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np

# Try to load attendance data
def load_attendance_data():
    """Load attendance records from file"""
    
    attendance_file = 'raw_data/attendance_records.json'
    
    if not os.path.exists(attendance_file):
        print("❌ Attendance records not found!")
        print("   Run: python3 attendance_analysis.py --import")
        return None
    
    # Use utf-8-sig to handle BOM (Byte Order Mark)
    with open(attendance_file, 'r', encoding='utf-8-sig') as f:
        data = json.load(f)
    
    return data['games']


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
    # If month is Jan-May, season is (year-1)-(year)
    # If month is Jun-Dec, season is (year)-(year+1)
    
    if month >= 1 and month <= 6:
        season = f"{year-1}-{str(year)[2:]}"
    else:
        season = f"{year}-{str(year+1)[2:]}"
    
    return season


def create_individual_team_graphs(games, output_dir='visualizations/teams'):
    """
    Create separate attendance trend graphs for each team
    Shows season-by-season data with different colors
    
    Args:
        games: List of game dicts with attendance data
        output_dir: Directory to save team graphs
    """
    
    print("📊 Creating individual team attendance graphs...")
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Group games by home team
    team_data = {}
    
    for game in games:
        home_team = game['home_team']
        date = datetime.strptime(game['date'], '%Y-%m-%d')
        attendance = game['attendance']
        season = get_season_from_date(game['date'])
        venue = game.get('venue', 'Unknown Venue')
        opponent = game.get('visitor_team', 'Unknown')
        
        if home_team not in team_data:
            team_data[home_team] = []
        
        team_data[home_team].append({
            'date': date,
            'attendance': attendance,
            'season': season,
            'venue': venue,
            'opponent': opponent
        })
    
    # Sort each team's data by date
    for team in team_data:
        team_data[team].sort(key=lambda x: x['date'])
    
    # Team colors and full names
    team_info = {
        'BOS': {'color': '#000000', 'name': 'Boston Fleet'},
        'MTL': {'color': '#862633', 'name': 'Montréal Victoire'},
        'TOR': {'color': '#00205B', 'name': 'Toronto Sceptres'},
        'MIN': {'color': '#154734', 'name': 'Minnesota Frost'},
        'OTT': {'color': '#C8102E', 'name': 'Ottawa Charge'},
        'NY': {'color': '#6CACE4', 'name': 'New York Sirens'},
        'SEA': {'color': '#0C4C8A', 'name': 'Seattle Surge'},
        'VAN': {'color': '#FFB81C', 'name': 'Vancouver Wolves'}
    }
    
    # Season colors for consistency
    season_colors = {
        '2023-24': '#1f77b4',  # Blue
        '2024-25': '#ff7f0e',  # Orange
        '2025-26': '#2ca02c'   # Green
    }
    
    created_files = []
    
    # Create a graph for each team
    for team_code, games_list in sorted(team_data.items()):
        
        # Get team info
        info = team_info.get(team_code, {'color': '#333333', 'name': team_code})
        team_name = info['name']
        team_color = info['color']
        
        # Group by season
        seasons = {}
        for game in games_list:
            season = game['season']
            if season not in seasons:
                seasons[season] = {'dates': [], 'attendance': []}
            seasons[season]['dates'].append(game['date'])
            seasons[season]['attendance'].append(game['attendance'])
        
        # Create figure
        fig, ax = plt.subplots(figsize=(14, 8))
        
        # Plot each season separately with different markers
        markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p']
        
        for i, (season, data) in enumerate(sorted(seasons.items())):
            season_color = season_colors.get(season, team_color)
            marker = markers[i % len(markers)]
            
            ax.plot(data['dates'], data['attendance'],
                   marker=marker, linewidth=2, markersize=8,
                   label=f"Season {season}", 
                   color=season_color, alpha=0.8,
                   linestyle='-' if len(seasons) == 1 else '--')
        
        # Calculate team statistics
        all_attendance = [g['attendance'] for g in games_list]
        avg_attendance = np.mean(all_attendance)
        max_attendance = max(all_attendance)
        min_attendance = min(all_attendance)
        
        # Add average line
        ax.axhline(y=avg_attendance, color=team_color, linestyle='--',
                  linewidth=2, alpha=0.5, 
                  label=f'Team Avg: {avg_attendance:,.0f}')
        
        # Formatting
        ax.set_xlabel('Date', fontsize=12, fontweight='bold')
        ax.set_ylabel('Attendance', fontsize=12, fontweight='bold')
        ax.set_title(f'{team_name} Home Attendance Trends\n({len(games_list)} games across {len(seasons)} season{"s" if len(seasons) > 1 else ""})',
                    fontsize=16, fontweight='bold', pad=20)
        
        # Format y-axis
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{int(x):,}'))
        
        # Format x-axis dates
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        plt.xticks(rotation=45, ha='right')
        
        # Grid
        ax.grid(True, alpha=0.3, linestyle='--')
        
        # Legend
        ax.legend(loc='best', fontsize=10, framealpha=0.9)
        
        # Add stats text box
        stats_text = f'Avg: {avg_attendance:,.0f}\n'
        stats_text += f'Max: {max_attendance:,}\n'
        stats_text += f'Min: {min_attendance:,}\n'
        stats_text += f'Games: {len(games_list)}'
        
        # Add venue info if consistent
        venues = list(set([g['venue'] for g in games_list]))
        if len(venues) == 1:
            venue_name = venues[0].split('|')[0].strip() if '|' in venues[0] else venues[0]
            stats_text += f'\n\nVenue:\n{venue_name}'
        
        ax.text(0.02, 0.98, stats_text,
               transform=ax.transAxes,
               fontsize=10,
               verticalalignment='top',
               horizontalalignment='left',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
        
        plt.tight_layout()
        
        # Save
        filename = f'{output_dir}/{team_code}_{team_name.replace(" ", "_")}_attendance.png'
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        plt.close()
        
        created_files.append(filename)
        print(f"  ✅ {team_name}: {filename}")
    
    return created_files


def create_all_teams_comparison(games, output_file='visualizations/all_teams_overview.png'):
    """
    Create a single overview showing all teams together
    Small multiples style
    
    Args:
        games: List of game dicts
        output_file: Where to save
    """
    
    print("📊 Creating all teams overview (small multiples)...")
    
    # Group by team
    team_data = {}
    
    for game in games:
        home = game['home_team']
        if home not in team_data:
            team_data[home] = []
        
        team_data[home].append({
            'date': datetime.strptime(game['date'], '%Y-%m-%d'),
            'attendance': game['attendance'],
            'season': get_season_from_date(game['date'])
        })
    
    # Sort
    for team in team_data:
        team_data[team].sort(key=lambda x: x['date'])
    
    # Team info
    team_info = {
        'BOS': {'color': '#000000', 'name': 'Boston'},
        'MTL': {'color': '#862633', 'name': 'Montréal'},
        'TOR': {'color': '#00205B', 'name': 'Toronto'},
        'MIN': {'color': '#154734', 'name': 'Minnesota'},
        'OTT': {'color': '#C8102E', 'name': 'Ottawa'},
        'NY': {'color': '#6CACE4', 'name': 'New York'},
        'SEA': {'color': '#0C4C8A', 'name': 'Seattle'},
        'VAN': {'color': '#FFB81C', 'name': 'Vancouver'}
    }
    
    # Create 2x4 grid
    fig, axes = plt.subplots(2, 4, figsize=(20, 10))
    axes = axes.flatten()
    
    for idx, (team_code, games_list) in enumerate(sorted(team_data.items())):
        ax = axes[idx]
        
        info = team_info.get(team_code, {'color': '#333333', 'name': team_code})
        
        # Plot
        dates = [g['date'] for g in games_list]
        attendance = [g['attendance'] for g in games_list]
        
        ax.plot(dates, attendance, marker='o', linewidth=2, 
               markersize=4, color=info['color'], alpha=0.7)
        
        # Average line
        avg = np.mean(attendance)
        ax.axhline(y=avg, color=info['color'], linestyle='--', 
                  linewidth=1, alpha=0.5)
        
        # Formatting
        ax.set_title(f"{info['name']}\nAvg: {avg:,.0f}", 
                    fontsize=11, fontweight='bold')
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{int(x/1000)}k'))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b\n%Y'))
        ax.tick_params(axis='both', which='major', labelsize=8)
        ax.grid(True, alpha=0.3, linestyle='--')
    
    plt.suptitle('PWHL Home Attendance Trends - All Teams', 
                fontsize=18, fontweight='bold', y=0.98)
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  ✅ Saved to: {output_file}")
    
    return output_file


def create_team_comparison_bar(games, output_file='attendance_comparison_by_team.png'):
    """
    Create a bar chart comparing average attendance by team
    
    Args:
        games: List of game dicts
        output_file: Where to save
    """
    
    print("📊 Creating team comparison bar chart...")
    
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
    
    # Colors
    colors_map = {
        'BOS': '#000000',
        'MTL': '#862633',
        'TOR': '#00205B',
        'MIN': '#154734',
        'OTT': '#C8102E',
        'NY': '#6CACE4',
        'SEA': '#0C4C8A',
        'VAN': '#FFB81C'
    }
    bar_colors = [colors_map.get(t, '#333333') for t in teams]
    
    # Create plot
    fig, ax = plt.subplots(figsize=(12, 7))
    
    bars = ax.bar(teams, averages, color=bar_colors, alpha=0.8, edgecolor='black')
    
    # Add value labels on bars
    for bar, avg, team in zip(bars, averages, teams):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(avg):,}\n({team_counts[team]} games)',
                ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    # Formatting
    ax.set_xlabel('Team', fontsize=12, fontweight='bold')
    ax.set_ylabel('Average Attendance', fontsize=12, fontweight='bold')
    ax.set_title('PWHL Average Home Attendance by Team', 
                 fontsize=16, fontweight='bold', pad=20)
    
    # Format y-axis
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{int(x):,}'))
    
    # Grid
    ax.grid(True, alpha=0.3, linestyle='--', axis='y')
    
    # Add league average line
    league_avg = np.mean(averages)
    ax.axhline(y=league_avg, color='red', linestyle='--', 
               linewidth=2, alpha=0.7, label=f'League Avg: {league_avg:,.0f}')
    ax.legend()
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"✅ Saved to: {output_file}")
    
    return fig


def create_attendance_distribution(games, output_file='attendance_distribution.png'):
    """
    Create a histogram showing distribution of attendance
    
    Args:
        games: List of game dicts
        output_file: Where to save
    """
    
    print("📊 Creating attendance distribution histogram...")
    
    attendances = [game['attendance'] for game in games]
    
    fig, ax = plt.subplots(figsize=(12, 7))
    
    # Create histogram
    n, bins, patches = ax.hist(attendances, bins=20, 
                               color='#0C4C8A', alpha=0.7, 
                               edgecolor='black', linewidth=1.2)
    
    # Color bars by height (gradient effect)
    cm = plt.cm.Blues
    bin_centers = 0.5 * (bins[:-1] + bins[1:])
    col = bin_centers - min(bin_centers)
    col /= max(col)
    
    for c, p in zip(col, patches):
        plt.setp(p, 'facecolor', cm(c))
    
    # Add mean and median lines
    mean_att = np.mean(attendances)
    median_att = np.median(attendances)
    
    ax.axvline(mean_att, color='red', linestyle='--', 
               linewidth=2, label=f'Mean: {mean_att:,.0f}')
    ax.axvline(median_att, color='green', linestyle='--', 
               linewidth=2, label=f'Median: {median_att:,.0f}')
    
    # Formatting
    ax.set_xlabel('Attendance', fontsize=12, fontweight='bold')
    ax.set_ylabel('Number of Games', fontsize=12, fontweight='bold')
    ax.set_title('PWHL Attendance Distribution', 
                 fontsize=16, fontweight='bold', pad=20)
    
    # Format x-axis
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{int(x):,}'))
    
    # Grid
    ax.grid(True, alpha=0.3, linestyle='--', axis='y')
    
    # Legend
    ax.legend(fontsize=11)
    
    # Add stats text box
    stats_text = f'Total Games: {len(attendances)}\n'
    stats_text += f'Min: {min(attendances):,}\n'
    stats_text += f'Max: {max(attendances):,}\n'
    stats_text += f'Std Dev: {np.std(attendances):,.0f}'
    
    ax.text(0.98, 0.97, stats_text,
            transform=ax.transAxes,
            fontsize=10,
            verticalalignment='top',
            horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"✅ Saved to: {output_file}")
    
    return fig


def create_all_visualizations():
    """Create all attendance visualizations"""
    
    print("\n🎨 PWHL ATTENDANCE VISUALIZATIONS")
    print("=" * 60)
    
    # Load data
    games = load_attendance_data()
    
    if not games:
        return False
    
    print(f"✓ Loaded {len(games)} games with attendance data")
    
    # Determine season range
    seasons = list(set([get_season_from_date(g['date']) for g in games]))
    print(f"✓ Seasons covered: {', '.join(sorted(seasons))}\n")
    
    # Create output directories
    os.makedirs('visualizations', exist_ok=True)
    os.makedirs('visualizations/teams', exist_ok=True)
    
    # Generate visualizations
    try:
        # 1. Individual team graphs (8 separate files)
        print("\n📊 Creating individual team graphs...")
        print("-" * 60)
        team_files = create_individual_team_graphs(games)
        print(f"✅ Created {len(team_files)} team-specific graphs\n")
        
        # 2. All teams overview (small multiples)
        all_teams_file = create_all_teams_comparison(games)
        print()
        
        # 3. Team comparison bar chart
        create_team_comparison_bar(games, 'visualizations/attendance_comparison_by_team.png')
        print()
        
        # 4. Attendance distribution
        create_attendance_distribution(games, 'visualizations/attendance_distribution.png')
        print()
        
        print("=" * 60)
        print("✅ ALL VISUALIZATIONS CREATED!")
        print("\n📁 Files saved:")
        print("\n  Individual Team Graphs (8 files):")
        for f in team_files:
            print(f"    - {f}")
        print("\n  Overview & Analysis:")
        print(f"    - visualizations/all_teams_overview.png")
        print(f"    - visualizations/attendance_comparison_by_team.png")
        print(f"    - visualizations/attendance_distribution.png")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error creating visualizations: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    import sys
    
    # Check for matplotlib
    try:
        import matplotlib
    except ImportError:
        print("❌ matplotlib not installed!")
        print("   Install: pip install matplotlib")
        sys.exit(1)
    
    # Create visualizations
    success = create_all_visualizations()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()