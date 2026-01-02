"""
Quick analysis of home vs away team win rates in PWHL
Analyzes historical game data to determine if home ice advantage exists
"""

import sys
import os
import json
from datetime import datetime

# Add pwhl_analytics_db to path
script_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(script_dir, 'pwhl_analytics_db')
sys.path.insert(0, db_path)

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from db_models import Game, Team

# Database configuration
DATABASE_URL = 'postgresql://postgres:SecurePassword@localhost/pwhl_analytics'
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


def analyze_home_away_performance():
    """
    Analyze home vs away win rates across all completed games
    """
    session = Session()

    try:
        # Get all completed games
        games = session.query(Game).filter(
            Game.game_status == 'final',
            Game.home_score.isnot(None),
            Game.away_score.isnot(None)
        ).all()

        if not games:
            print("No completed games found in database")
            return

        # Track results
        total_games = len(games)
        home_wins = 0
        away_wins = 0
        ties = 0

        home_goals_total = 0
        away_goals_total = 0

        # Track by season
        season_stats = {}

        for game in games:
            # Count wins
            if game.home_score > game.away_score:
                home_wins += 1
            elif game.away_score > game.home_score:
                away_wins += 1
            else:
                ties += 1

            # Track goals
            home_goals_total += game.home_score
            away_goals_total += game.away_score

            # Track by season
            season = game.season_id
            if season not in season_stats:
                season_stats[season] = {
                    'games': 0,
                    'home_wins': 0,
                    'away_wins': 0,
                    'ties': 0,
                    'home_goals': 0,
                    'away_goals': 0
                }

            season_stats[season]['games'] += 1
            season_stats[season]['home_goals'] += game.home_score
            season_stats[season]['away_goals'] += game.away_score

            if game.home_score > game.away_score:
                season_stats[season]['home_wins'] += 1
            elif game.away_score > game.home_score:
                season_stats[season]['away_wins'] += 1
            else:
                season_stats[season]['ties'] += 1

        # Calculate percentages
        home_win_pct = (home_wins / total_games) * 100 if total_games > 0 else 0
        away_win_pct = (away_wins / total_games) * 100 if total_games > 0 else 0
        tie_pct = (ties / total_games) * 100 if total_games > 0 else 0

        avg_home_goals = home_goals_total / total_games if total_games > 0 else 0
        avg_away_goals = away_goals_total / total_games if total_games > 0 else 0

        # Print results
        print("=" * 60)
        print("PWHL HOME vs AWAY PERFORMANCE ANALYSIS")
        print("=" * 60)
        print()
        print(f"Total Games Analyzed: {total_games}")
        print()
        print("-" * 60)
        print("WIN RATES")
        print("-" * 60)
        print(f"Home Team Wins:  {home_wins:4d} ({home_win_pct:5.1f}%)")
        print(f"Away Team Wins:  {away_wins:4d} ({away_win_pct:5.1f}%)")
        if ties > 0:
            print(f"Ties:            {ties:4d} ({tie_pct:5.1f}%)")
        print()

        print("-" * 60)
        print("SCORING AVERAGES")
        print("-" * 60)
        print(f"Avg Home Team Goals: {avg_home_goals:.2f}")
        print(f"Avg Away Team Goals: {avg_away_goals:.2f}")
        print(f"Goal Differential:   {avg_home_goals - avg_away_goals:+.2f} (home advantage)")
        print()

        # Season breakdown
        print("-" * 60)
        print("BY SEASON BREAKDOWN")
        print("-" * 60)

        for season in sorted(season_stats.keys()):
            stats = season_stats[season]
            s_home_pct = (stats['home_wins'] / stats['games']) * 100 if stats['games'] > 0 else 0
            s_away_pct = (stats['away_wins'] / stats['games']) * 100 if stats['games'] > 0 else 0
            s_avg_home = stats['home_goals'] / stats['games'] if stats['games'] > 0 else 0
            s_avg_away = stats['away_goals'] / stats['games'] if stats['games'] > 0 else 0

            print(f"\nSeason {season}:")
            print(f"  Games: {stats['games']}")
            print(f"  Home Wins: {stats['home_wins']} ({s_home_pct:.1f}%)")
            print(f"  Away Wins: {stats['away_wins']} ({s_away_pct:.1f}%)")
            print(f"  Avg Goals: Home {s_avg_home:.2f} | Away {s_avg_away:.2f}")

        print()
        print("=" * 60)
        print("INTERPRETATION")
        print("=" * 60)

        # Determine if home advantage exists
        if home_win_pct > 52:  # More than random + small margin
            advantage_strength = "strong" if home_win_pct > 60 else "moderate"
            print(f"[+] {advantage_strength.upper()} HOME ICE ADVANTAGE detected")
            print(f"  Home teams win {home_win_pct - 50:.1f} percentage points above 50%")
        elif home_win_pct > 50:
            print("[+] SLIGHT HOME ICE ADVANTAGE detected")
            print(f"  Home teams win {home_win_pct - 50:.1f} percentage points above 50%")
        elif home_win_pct < 48:
            print("[!] NO HOME ICE ADVANTAGE - Away teams winning more")
        else:
            print("[~] NO CLEAR ADVANTAGE - Roughly even split")

        print()
        print("For predictive modeling:")
        print(f"  - Baseline 'always pick home' accuracy: {home_win_pct:.1f}%")
        print(f"  - Your model should beat: {max(home_win_pct, away_win_pct):.1f}%")
        print("=" * 60)

    finally:
        session.close()

def analyze_home_away_by_team(return_data=False, save_to_file=False):
    """
    Analyze home vs away performance broken down by team
    Shows which teams have strongest/weakest home ice advantage

    Args:
        return_data: If True, return the team_results data structure
        save_to_file: If True, save results to JSON file

    Returns:
        dict: Team home/away statistics if return_data=True, otherwise None
    """
    # Initialize stats dictionary for all 8 PWHL teams
    team_stats = {
        'BOS': {
            'home_games': 0,
            'home_wins': 0,
            'away_games': 0,
            'away_wins': 0,
            'home_goals_for': 0,
            'home_goals_against': 0,
            'away_goals_for': 0,
            'away_goals_against': 0
        },
        'MTL': {
            'home_games': 0,
            'home_wins': 0,
            'away_games': 0,
            'away_wins': 0,
            'home_goals_for': 0,
            'home_goals_against': 0,
            'away_goals_for': 0,
            'away_goals_against': 0
        },
        'SEA': {
            'home_games': 0,
            'home_wins': 0,
            'away_games': 0,
            'away_wins': 0,
            'home_goals_for': 0,
            'home_goals_against': 0,
            'away_goals_for': 0,
            'away_goals_against': 0
        },
        'TOR': {
            'home_games': 0,
            'home_wins': 0,
            'away_games': 0,
            'away_wins': 0,
            'home_goals_for': 0,
            'home_goals_against': 0,
            'away_goals_for': 0,
            'away_goals_against': 0
        },
        'VAN': {
            'home_games': 0,
            'home_wins': 0,
            'away_games': 0,
            'away_wins': 0,
            'home_goals_for': 0,
            'home_goals_against': 0,
            'away_goals_for': 0,
            'away_goals_against': 0
        },
        'NY':{
            'home_games': 0,
            'home_wins': 0,
            'away_games': 0,
            'away_wins': 0,
            'home_goals_for': 0,
            'home_goals_against': 0,
            'away_goals_for': 0,
            'away_goals_against': 0
        },
        'OTT':{
            'home_games': 0,
            'home_wins': 0,
            'away_games': 0,
            'away_wins': 0,
            'home_goals_for': 0,
            'home_goals_against': 0,
            'away_goals_for': 0,
            'away_goals_against': 0
        },
        'MIN':{
            'home_games': 0,
            'home_wins': 0,
            'away_games': 0,
            'away_wins': 0,
            'home_goals_for': 0,
            'home_goals_against': 0,
            'away_goals_for': 0,
            'away_goals_against': 0
        }
    }

    # Team code to full name mapping for nice output
    team_names = {
        'BOS': 'Boston Fleet',
        'MTL': 'Montreal Victoire',
        'SEA': 'Seattle Torrent',
        'TOR': 'Toronto Sceptres',
        'VAN': 'Vancouver Goldeneyes',
        'NY': 'New York Sirens',
        'OTT': 'Ottawa Charge',
        'MIN': 'Minnesota Frost'
    }

    session = Session()

    try:
        # Get all completed games
        games = session.query(Game).filter(
            Game.game_status == 'final',
            Game.home_score.isnot(None),
            Game.away_score.isnot(None)
        ).all()

        if not games:
            print("No completed games found in database")
            return

        # Build a lookup dictionary: team_id -> team_code
        # This is needed because Game table only has team_id, not team_code
        team_lookup = {}
        teams = session.query(Team).all()
        for team in teams:
            team_lookup[team.team_id] = team.team_code

        # Loop through all games and collect stats
        for game in games:
            # Get team codes from team IDs
            home_team = team_lookup.get(game.home_team_id, 'UNK')
            away_team = team_lookup.get(game.away_team_id, 'UNK')

            # Skip if team code not found or not in our stats dict
            if home_team not in team_stats or away_team not in team_stats:
                continue

            # Update home team stats
            team_stats[home_team]['home_games'] += 1
            team_stats[home_team]['home_goals_for'] += game.home_score
            team_stats[home_team]['home_goals_against'] += game.away_score
            if game.home_score > game.away_score:
                team_stats[home_team]['home_wins'] += 1

            # Update away team stats
            team_stats[away_team]['away_games'] += 1
            team_stats[away_team]['away_goals_for'] += game.away_score
            team_stats[away_team]['away_goals_against'] += game.home_score
            if game.away_score > game.home_score:
                team_stats[away_team]['away_wins'] += 1

        # Calculate percentages and derived metrics for each team
        team_results = []
        for code, stats in team_stats.items():
            # Avoid division by zero
            home_win_pct = (stats['home_wins'] / stats['home_games'] * 100) if stats['home_games'] > 0 else 0
            away_win_pct = (stats['away_wins'] / stats['away_games'] * 100) if stats['away_games'] > 0 else 0

            home_gpg = stats['home_goals_for'] / stats['home_games'] if stats['home_games'] > 0 else 0
            away_gpg = stats['away_goals_for'] / stats['away_games'] if stats['away_games'] > 0 else 0

            home_gaa = stats['home_goals_against'] / stats['home_games'] if stats['home_games'] > 0 else 0
            away_gaa = stats['away_goals_against'] / stats['away_games'] if stats['away_games'] > 0 else 0

            # KEY METRIC: Home advantage gap (positive = better at home, negative = better on road)
            home_advantage_gap = home_win_pct - away_win_pct

            team_results.append({
                'code': code,
                'name': team_names.get(code, code),
                'home_record': f"{stats['home_wins']}-{stats['home_games'] - stats['home_wins']}",
                'away_record': f"{stats['away_wins']}-{stats['away_games'] - stats['away_wins']}",
                'home_win_pct': home_win_pct,
                'away_win_pct': away_win_pct,
                'home_advantage_gap': home_advantage_gap,
                'home_gpg': home_gpg,
                'away_gpg': away_gpg,
                'home_gaa': home_gaa,
                'away_gaa': away_gaa,
                'home_games': stats['home_games'],
                'away_games': stats['away_games']
            })

        # Sort by home advantage gap (highest to lowest)
        team_results.sort(key=lambda x: x['home_advantage_gap'], reverse=True)

        # Print results
        print("=" * 80)
        print("TEAM-BY-TEAM HOME vs AWAY PERFORMANCE")
        print("=" * 80)
        print()

        for team in team_results:
            print(f"{team['name']} ({team['code']}):")
            print(f"  Home: {team['home_record']:>6} ({team['home_win_pct']:5.1f}%) - {team['home_games']} games")
            print(f"  Away: {team['away_record']:>6} ({team['away_win_pct']:5.1f}%) - {team['away_games']} games")
            print(f"  Home Advantage Gap: {team['home_advantage_gap']:+6.1f} percentage points")
            print(f"  Goals/Game:  Home {team['home_gpg']:.2f} | Away {team['away_gpg']:.2f}")
            print(f"  Goals Against: Home {team['home_gaa']:.2f} | Away {team['away_gaa']:.2f}")
            print()

        # Key insights
        print("=" * 80)
        print("KEY INSIGHTS")
        print("=" * 80)

        strongest_home = team_results[0]
        weakest_home = team_results[-1]
        best_road = max(team_results, key=lambda x: x['away_win_pct'])
        worst_road = min(team_results, key=lambda x: x['away_win_pct'])

        print(f"Strongest Home Ice Advantage: {strongest_home['name']}")
        print(f"  ({strongest_home['home_advantage_gap']:+.1f}% gap - {strongest_home['home_win_pct']:.1f}% home vs {strongest_home['away_win_pct']:.1f}% away)")
        print()
        print(f"Weakest/Most Road-Friendly: {weakest_home['name']}")
        print(f"  ({weakest_home['home_advantage_gap']:+.1f}% gap - {weakest_home['home_win_pct']:.1f}% home vs {weakest_home['away_win_pct']:.1f}% away)")
        print()
        print(f"Best Road Team: {best_road['name']} ({best_road['away_win_pct']:.1f}% away win rate)")
        print(f"Worst Road Team: {worst_road['name']} ({worst_road['away_win_pct']:.1f}% away win rate)")
        print()
        print("=" * 80)
        print("MODEL IMPLICATIONS:")
        print("=" * 80)

        # Check if home advantage varies significantly by team
        gaps = [t['home_advantage_gap'] for t in team_results]
        gap_range = max(gaps) - min(gaps)

        if gap_range > 20:
            print("HOME ADVANTAGE VARIES SIGNIFICANTLY BY TEAM (>20% range)")
            print("  -> Recommendation: Use team-specific home advantage features")
            print(f"  -> Range: {min(gaps):.1f}% to {max(gaps):.1f}%")
        elif gap_range > 10:
            print("HOME ADVANTAGE VARIES MODERATELY BY TEAM (10-20% range)")
            print("  -> Recommendation: Consider team-specific features or interaction terms")
            print(f"  -> Range: {min(gaps):.1f}% to {max(gaps):.1f}%")
        else:
            print("HOME ADVANTAGE IS RELATIVELY CONSISTENT ACROSS TEAMS (<10% range)")
            print("  -> Recommendation: Simple binary 'is_home' feature should be sufficient")
            print(f"  -> Range: {min(gaps):.1f}% to {max(gaps):.1f}%")
        print("=" * 80)

        # Save to file if requested
        if save_to_file:
            output_data = {
                'generated_at': datetime.now().isoformat(),
                'total_games_analyzed': len(games),
                'league_home_advantage': 5.1,  # From overall analysis
                'teams': {}
            }

            for team in team_results:
                output_data['teams'][team['code']] = {
                    'name': team['name'],
                    'home_win_pct': round(team['home_win_pct'], 2),
                    'away_win_pct': round(team['away_win_pct'], 2),
                    'home_advantage_gap': round(team['home_advantage_gap'], 2),
                    'home_games': team['home_games'],
                    'away_games': team['away_games'],
                    'total_games': team['home_games'] + team['away_games'],
                    'home_record': team['home_record'],
                    'away_record': team['away_record'],
                    'home_goals_per_game': round(team['home_gpg'], 2),
                    'away_goals_per_game': round(team['away_gpg'], 2),
                    'home_goals_against_per_game': round(team['home_gaa'], 2),
                    'away_goals_against_per_game': round(team['away_gaa'], 2)
                }

            # Save to JSON file
            output_file = 'team_home_away_stats.json'
            with open(output_file, 'w') as f:
                json.dump(output_data, f, indent=2)
            print(f"\n[SAVED] Team home/away statistics saved to: {output_file}")

        # Return data if requested
        if return_data:
            return team_results

    finally:
        session.close()


def get_team_home_away_stats(team_code):
    """
    Get home/away statistics for a specific team
    Helper function for use in prediction models

    Args:
        team_code: Team code (e.g., 'BOS', 'MTL')

    Returns:
        dict: Team's home/away stats or None if not found
    """
    team_results = analyze_home_away_by_team(return_data=True)

    if team_results:
        for team in team_results:
            if team['code'] == team_code:
                return team

    return None


if __name__ == "__main__":
    # Run overall home/away analysis
    analyze_home_away_performance()

    print("\n" * 3)

    # Run team-specific home/away analysis and save results
    analyze_home_away_by_team(save_to_file=True)
