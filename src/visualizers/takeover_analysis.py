#!/usr/bin/env python3
"""
PWHL Takeover Games Analysis
Analyzes and visualizes attendance at neutral-site "takeover" games
Updated to use PostgreSQL database
"""

import os
import sys
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.database.db_queries import Session
from src.database.db_models import Game, Team

# PWHL home venues (these are NOT takeover games)
PWHL_HOME_VENUES = [
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


def load_attendance_data_from_db(season_id=None):
    """
    Load attendance records from database

    Args:
        season_id: Optional season ID to filter

    Returns:
        List of game dicts with attendance data
    """
    session = Session()
    try:
        from sqlalchemy.orm import aliased

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

        results = query.order_by(Game.date).all()

        games = []
        for game, home_team, away_team in results:
            games.append({
                'game_id': game.game_id,
                'date': game.date.strftime('%Y-%m-%d'),
                'home_team': home_team.team_code,
                'visitor_team': away_team.team_code,
                'home_team_name': home_team.team_name,
                'visitor_team_name': away_team.team_name,
                'attendance': game.attendance,
                'venue': game.venue if game.venue else 'Unknown',
                'home_score': game.home_score,
                'away_score': game.away_score,
                'final_score': f"{game.away_score}-{game.home_score}",
                'season_id': game.season_id
            })

        return games
    finally:
        session.close()


def identify_takeover_games(games):
    """
    Identify takeover games (neutral site games)

    Takeover games are those played in cities without a PWHL team

    Args:
        games: List of game dicts

    Returns:
        List of takeover game dicts with additional info
    """

    takeover_games = []

    for game in games:
        venue = game.get('venue', '')
        game_date = game.get('date', '')

        # Extract venue name (before the | if present)
        venue_name = venue.split('|')[0].strip() if '|' in venue else venue.strip()

        # Special handling: Climate Pledge Arena before Seattle team existed
        if 'Climate Pledge Arena' in venue_name and game_date < '2025-11-01':
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
                'final_score': game['final_score']
            })
            continue

        # Check if this is a PWHL home venue
        is_home_venue = any(home_venue.lower() in venue_name.lower()
                           for home_venue in PWHL_HOME_VENUES)

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
                'final_score': game['final_score']
            })

    return takeover_games


def print_takeover_summary(takeover_games):
    """
    Print a text summary of takeover games

    Args:
        takeover_games: List of takeover game dicts
    """

    print("\n" + "=" * 70)
    print("TAKEOVER GAMES SUMMARY")
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


def export_takeover_csv(takeover_games, output_file='outputs/visualizations/takeover_games.csv'):
    """
    Export takeover games to CSV for easy analysis

    Args:
        takeover_games: List of takeover game dicts
        output_file: Where to save
    """

    print("Exporting takeover games to CSV...")

    if not takeover_games:
        print("  No takeover games found!")
        return None

    import csv

    # Sort by date
    takeover_games.sort(key=lambda x: x['date'])

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

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

    print(f"  Saved to: {output_file}")

    return output_file


def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description='PWHL Takeover Games Analysis')
    parser.add_argument('--season', type=int, help='Season ID to filter (default: all seasons)')

    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("PWHL TAKEOVER GAMES ANALYSIS")
    print("=" * 70)

    # Load data
    print("\nLoading attendance data from database...")
    games = load_attendance_data_from_db(season_id=args.season)

    if not games:
        print("No games with attendance data found")
        return 1

    print(f"Loaded {len(games)} total games")
    if args.season:
        print(f"Season filter: {args.season}")

    # Identify takeover games
    print("\nIdentifying takeover games (neutral-site games)...")
    takeover_games = identify_takeover_games(games)

    if not takeover_games:
        print("\nNo takeover games found in the data!")
        print("All games appear to be at home venues.")
        return 0

    print(f"Found {len(takeover_games)} takeover games\n")

    # Export CSV
    try:
        export_takeover_csv(takeover_games)
        print()

        # Text summary
        print_takeover_summary(takeover_games)

        print("\n" + "=" * 70)
        print("TAKEOVER GAMES ANALYSIS COMPLETE!")
        print("=" * 70)

        return 0

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
