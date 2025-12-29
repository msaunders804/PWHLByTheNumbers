#!/usr/bin/env python3
"""
PWHL Takeover Games Analysis
Analyzes and visualizes attendance at neutral-site "takeover" games
"""

import json
import os
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

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


def identify_takeover_games(games):
    """
    Identify takeover games (neutral site games)
    
    Takeover games are those played in cities without a PWHL team
    
    Args:
        games: List of game dicts
    
    Returns:
        List of takeover game dicts with additional info
    """
    
    # PWHL home venues (these are NOT takeover games)
    pwhl_home_venues = [
        'Place Bell',                # Montreal
        "Bell Centre",             # Montreal
        "Verdun Auditorium",      # Montreal
        'Coca-Cola Coliseum',        # Toronto
        "Mattamy Athletic Centre", # Toronto
        "Scotiabank Arena",          # Toronto
        'Tsongas Center',            # Boston
        'Agganis Arena',          # Boston
        'TD Place',            # Ottawa
        "Grand Casino Arena", #St Paul/MIN
        "Canadian Tire Centre",    # Ottawa
        'Prudential Center',         # NY Sirens
        'Xcel Energy Center',        # Minnesota
        'Climate Pledge Arena',      # Seattle
        'Pacific Coliseum',           # Vancouver
        'Total Mortgage Arena',      # CT/NY
        'UBS Arena',              # NY
        '3M Arena at Mariucci',    # Minnesota
    ]
    
    takeover_games = []
    
    for game in games:
        venue = game.get('venue', '') 
        game_date = game.get('date', '')
        
        # Extract venue name (before the | if present)
        venue_name = venue.split('|')[0].strip() if '|' in venue else venue.strip()

        if 'Climate Pledge Arena' in venue_name and game_date == '2025-01-05':
            # This IS a takeover game (before Seattle team existed)
            city = "Seattle"
            if '|' in venue:
                location = venue.split('|')[1].strip()
                city = location.split(',')[0].strip()
            
            takeover_games.append({
                'game_id': game['game_id'],
                'date': game['date'],
                'home_team': game['home_team'],
                'visitor_team': game['visitor_team'],
                'venue': venue,
                'city': city,
                'attendance': game['attendance'],
                'final_score': game.get('final_score', 'Unknown')
            })
            continue  # Skip normal home 

        # Check if this is a PWHL home venue
        is_home_venue = any(home_venue.lower() in venue_name.lower() 
                           for home_venue in pwhl_home_venues)
        
        if not is_home_venue:
            # This is a takeover game!
            
            # Extract city from venue
            # Format is usually "Arena Name | City, State/Province"
            city = "Unknown"
            if '|' in venue:
                location = venue.split('|')[1].strip()
                city = location.split(',')[0].strip()
            
            takeover_games.append({
                'game_id': game['game_id'],
                'date': game['date'],
                'home_team': game['home_team'],
                'visitor_team': game['visitor_team'],
                'venue': venue,
                'city': city,
                'attendance': game['attendance'],
                'final_score': game.get('final_score', 'Unknown')
            })
    
    return takeover_games


def create_takeover_table_visualization(takeover_games, output_file='visualizations/takeover_games_table.png'):
    """
    Create a professional data table showing takeover games
    
    Args:
        takeover_games: List of takeover game dicts
        output_file: Where to save
    """
    
    print("📊 Creating takeover games table...")
    
    if not takeover_games:
        print("  ⚠️  No takeover games found!")
        return None
    
    # Sort by attendance (descending)
    takeover_games.sort(key=lambda x: x['attendance'], reverse=True)
    
    # Prepare data for table
    table_data = []
    
    for i, game in enumerate(takeover_games, 1):
        date_obj = datetime.strptime(game['date'], '%Y-%m-%d')
        date_str = date_obj.strftime('%b %d, %Y')
        
        # Get venue name (before the |)
        venue_name = game['venue'].split('|')[0].strip() if '|' in game['venue'] else game['venue']
        
        row = [
            str(i),  # Rank
            date_str,
            f"{game['visitor_team']} @ {game['home_team']}",
            game['city'],
            venue_name,
            f"{game['attendance']:,}",
            game['final_score']
        ]
        table_data.append(row)
    
    # Create figure
    fig, ax = plt.subplots(figsize=(16, len(takeover_games) * 0.5 + 2))
    ax.axis('tight')
    ax.axis('off')
    
    # Column headers
    headers = ['#', 'Date', 'Matchup', 'City', 'Venue', 'Attendance', 'Score']
    
    # Create table
    table = ax.table(cellText=table_data,
                     colLabels=headers,
                     cellLoc='left',
                     loc='center',
                     colWidths=[0.05, 0.12, 0.15, 0.12, 0.25, 0.12, 0.10])
    
    # Style the table
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 2)
    
    # Header styling
    for i in range(len(headers)):
        cell = table[(0, i)]
        cell.set_facecolor('#0C4C8A')
        cell.set_text_props(weight='bold', color='white', fontsize=10)
    
    # Row styling (alternating colors)
    for i in range(1, len(table_data) + 1):
        for j in range(len(headers)):
            cell = table[(i, j)]
            
            # Alternating row colors
            if i % 2 == 0:
                cell.set_facecolor('#f0f0f0')
            else:
                cell.set_facecolor('white')
            
            # Highlight attendance column
            if j == 5:  # Attendance column
                cell.set_text_props(weight='bold')
                attendance = int(table_data[i-1][5].replace(',', ''))
                
                # Color code by attendance
                if attendance >= 10000:
                    cell.set_facecolor('#d4edda')  # Green
                elif attendance >= 8000:
                    cell.set_facecolor('#fff3cd')  # Yellow
                else:
                    cell.set_facecolor('#f8d7da')  # Red
    
    # Title
    title_text = f'PWHL Takeover Games - Neutral Site Attendance\n'
    title_text += f'Total Games: {len(takeover_games)} | '
    avg_attendance = np.mean([g['attendance'] for g in takeover_games])
    title_text += f'Average Attendance: {avg_attendance:,.0f}'
    
    plt.title(title_text, fontsize=16, fontweight='bold', pad=20)
    
    # Legend for attendance colors
    green_patch = mpatches.Patch(color='#d4edda', label='10,000+ attendance')
    yellow_patch = mpatches.Patch(color='#fff3cd', label='8,000-9,999 attendance')
    red_patch = mpatches.Patch(color='#f8d7da', label='< 8,000 attendance')
    
    plt.legend(handles=[green_patch, yellow_patch, red_patch],
              loc='upper right', bbox_to_anchor=(1.0, -0.05),
              ncol=3, frameon=False, fontsize=9)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  ✅ Saved to: {output_file}")
    
    return output_file


def create_takeover_bar_chart(takeover_games, output_file='visualizations/takeover_games_by_city.png'):
    """
    Create bar chart showing takeover attendance by city
    
    Args:
        takeover_games: List of takeover game dicts
        output_file: Where to save
    """
    
    print("📊 Creating takeover games bar chart...")
    
    if not takeover_games:
        print("  ⚠️  No takeover games found!")
        return None
    
    # Group by city
    city_data = {}
    
    for game in takeover_games:
        city = game['city']
        
        if city not in city_data:
            city_data[city] = {
                'games': [],
                'total_attendance': 0,
                'count': 0
            }
        
        city_data[city]['games'].append(game)
        city_data[city]['total_attendance'] += game['attendance']
        city_data[city]['count'] += 1
    
    # Calculate averages
    for city in city_data:
        city_data[city]['avg_attendance'] = city_data[city]['total_attendance'] / city_data[city]['count']
    
    # Sort by average attendance
    sorted_cities = sorted(city_data.items(), 
                          key=lambda x: x[1]['avg_attendance'], 
                          reverse=True)
    
    # Prepare data
    cities = [city for city, _ in sorted_cities]
    avg_attendances = [data['avg_attendance'] for _, data in sorted_cities]
    game_counts = [data['count'] for _, data in sorted_cities]
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Create bars
    bars = ax.bar(cities, avg_attendances, color='#0C4C8A', alpha=0.8, edgecolor='black')
    
    # Color bars by attendance
    for bar, avg in zip(bars, avg_attendances):
        if avg >= 10000:
            bar.set_color('#154734')  # Dark green
        elif avg >= 8000:
            bar.set_color('#FFB81C')  # Gold
        else:
            bar.set_color('#C8102E')  # Red
    
    # Add value labels and game counts
    for i, (bar, avg, count) in enumerate(zip(bars, avg_attendances, game_counts)):
        height = bar.get_height()
        
        # Attendance number
        ax.text(bar.get_x() + bar.get_width()/2., height,
               f'{int(avg):,}',
               ha='center', va='bottom', fontsize=11, fontweight='bold')
        
        # Game count
        ax.text(bar.get_x() + bar.get_width()/2., height * 0.5,
               f'{count} game{"s" if count > 1 else ""}',
               ha='center', va='center', fontsize=9, 
               color='white', fontweight='bold',
               bbox=dict(boxstyle='round,pad=0.3', facecolor='black', alpha=0.7))
    
    # Formatting
    ax.set_xlabel('City', fontsize=12, fontweight='bold')
    ax.set_ylabel('Average Attendance', fontsize=12, fontweight='bold')
    ax.set_title('PWHL Takeover Games - Average Attendance by City', 
                fontsize=16, fontweight='bold', pad=20)
    
    # Format y-axis
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{int(x):,}'))
    
    # Rotate x-axis labels if needed
    if len(cities) > 5:
        plt.xticks(rotation=45, ha='right')
    
    # Grid
    ax.grid(True, alpha=0.3, linestyle='--', axis='y')
    
    # Add league average line for comparison
    all_games = load_attendance_data()
    if all_games:
        league_avg = np.mean([g['attendance'] for g in all_games])
        ax.axhline(y=league_avg, color='red', linestyle='--',
                  linewidth=2, alpha=0.7,
                  label=f'League Avg (all games): {league_avg:,.0f}')
        ax.legend(fontsize=10)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  ✅ Saved to: {output_file}")
    
    return output_file


def export_takeover_csv(takeover_games, output_file='visualizations/takeover_games.csv'):
    """
    Export takeover games to CSV for easy analysis
    
    Args:
        takeover_games: List of takeover game dicts
        output_file: Where to save
    """
    
    print("📄 Exporting takeover games to CSV...")
    
    if not takeover_games:
        print("  ⚠️  No takeover games found!")
        return None
    
    import csv
    
    # Sort by date
    takeover_games.sort(key=lambda x: x['date'])
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Headers
        writer.writerow([
            'Game ID', 'Date', 'Home Team', 'Visitor Team', 
            'City', 'Venue', 'Attendance', 'Final Score'
        ])
        
        # Data
        for game in takeover_games:
            writer.writerow([
                game['game_id'],
                game['date'],
                game['home_team'],
                game['visitor_team'],
                game['city'],
                game['venue'],
                game['attendance'],
                game['final_score']
            ])
    
    print(f"  ✅ Saved to: {output_file}")
    
    return output_file


def print_takeover_summary(takeover_games):
    """
    Print a text summary of takeover games
    
    Args:
        takeover_games: List of takeover game dicts
    """
    
    print("\n" + "=" * 70)
    print("📊 TAKEOVER GAMES SUMMARY")
    print("=" * 70)
    
    if not takeover_games:
        print("No takeover games found in the data.")
        return
    
    # Overall stats
    total_games = len(takeover_games)
    total_attendance = sum(g['attendance'] for g in takeover_games)
    avg_attendance = total_attendance / total_games
    max_game = max(takeover_games, key=lambda x: x['attendance'])
    min_game = min(takeover_games, key=lambda x: x['attendance'])
    
    print(f"\nTotal Takeover Games: {total_games}")
    print(f"Total Attendance: {total_attendance:,}")
    print(f"Average Attendance: {avg_attendance:,.0f}")
    print(f"\nHighest Attended Game:")
    print(f"  {max_game['visitor_team']} @ {max_game['home_team']}")
    print(f"  {max_game['venue']}")
    print(f"  {max_game['date']} - {max_game['attendance']:,} fans")
    print(f"\nLowest Attended Game:")
    print(f"  {min_game['visitor_team']} @ {min_game['home_team']}")
    print(f"  {min_game['venue']}")
    print(f"  {min_game['date']} - {min_game['attendance']:,} fans")
    
    # By city
    print("\n" + "-" * 70)
    print("GAMES BY CITY:")
    print("-" * 70)
    
    city_summary = {}
    for game in takeover_games:
        city = game['city']
        if city not in city_summary:
            city_summary[city] = []
        city_summary[city].append(game)
    
    for city in sorted(city_summary.keys()):
        games = city_summary[city]
        city_total = sum(g['attendance'] for g in games)
        city_avg = city_total / len(games)
        
        print(f"\n{city}:")
        print(f"  Games: {len(games)}")
        print(f"  Avg Attendance: {city_avg:,.0f}")
        
        for game in sorted(games, key=lambda x: x['date']):
            print(f"    • {game['date']}: {game['visitor_team']} @ {game['home_team']} "
                  f"- {game['attendance']:,} fans")


def main():
    """Main function"""
    
    print("\n🏟️  PWHL TAKEOVER GAMES ANALYSIS")
    print("=" * 70)
    
    # Load data
    games = load_attendance_data()
    
    if not games:
        return 1
    
    print(f"✓ Loaded {len(games)} total games\n")
    
    # Identify takeover games
    print("🔍 Identifying takeover games (neutral-site games)...")
    takeover_games = identify_takeover_games(games)
    
    if not takeover_games:
        print("\n❌ No takeover games found in the data!")
        print("   All games appear to be at home venues.")
        return 0
    
    print(f"✓ Found {len(takeover_games)} takeover games\n")
    
    # Create visualizations
    os.makedirs('visualizations', exist_ok=True)
    
    try:
        # Table visualization
        create_takeover_table_visualization(takeover_games)
        print()
        
        # Bar chart by city
        create_takeover_bar_chart(takeover_games)
        print()
        
        # CSV export
        export_takeover_csv(takeover_games)
        print()
        
        # Text summary
        #print_takeover_summary(takeover_games)
        
        print("\n" + "=" * 70)
        print("✅ TAKEOVER GAMES ANALYSIS COMPLETE!")
        print("\n📁 Files created:")
        print("  - visualizations/takeover_games_table.png")
        print("  - visualizations/takeover_games_by_city.png")
        print("  - visualizations/takeover_games.csv")
        print("=" * 70)
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())