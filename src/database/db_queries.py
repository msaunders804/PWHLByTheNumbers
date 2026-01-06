"""
Database Query Module for PWHL Analytics
Provides functions to query the PostgreSQL database for game data
"""

import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path for relative imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, desc, func
from sqlalchemy.orm import sessionmaker
from database.db_models import Game, Team, Player, PlayerGameStats, GoalieGameStats
from database.load_data import load_game_data
from content.firsts_detector import get_all_firsts_for_game

# PWHL home venues (from takeover_analysis.py)
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

# Database configuration
DATABASE_URL = 'postgresql://postgres:SecurePassword@localhost/pwhl_analytics'
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


def get_most_recent_completed_game():
    """
    Get the most recent completed game from the database

    Returns:
        Dict with game info or None if no games found
    """
    session = Session()
    try:
        # Query for most recent game (order by date DESC, then game_id DESC for same-day games)
        game = session.query(Game).filter(
            Game.game_status == 'final'
        ).order_by(desc(Game.date), desc(Game.game_id)).first()

        if not game:
            return None

        # Get team info
        home_team = session.query(Team).filter(Team.team_id == game.home_team_id).first()
        away_team = session.query(Team).filter(Team.team_id == game.away_team_id).first()

        return {
            'game_id': game.game_id,
            'date': game.date.strftime('%Y-%m-%d'),
            'home_team': home_team.team_code if home_team else 'UNK',
            'home_team_name': home_team.team_name if home_team else 'Unknown',
            'away_team': away_team.team_code if away_team else 'UNK',
            'away_team_name': away_team.team_name if away_team else 'Unknown',
            'home_score': game.home_score,
            'away_score': game.away_score,
            'attendance': game.attendance
        }
    finally:
        session.close()


def check_game_exists_in_db(game_id):
    """
    Check if a game exists in the database

    Args:
        game_id: Game ID to check

    Returns:
        Boolean indicating if game exists
    """
    session = Session()
    try:
        game = session.query(Game).filter(Game.game_id == game_id).first()
        return game is not None
    finally:
        session.close()


def ensure_game_in_db(game_id):
    """
    Ensure a game is in the database, downloading if necessary

    Args:
        game_id: Game ID to ensure exists

    Returns:
        Boolean indicating success
    """
    if check_game_exists_in_db(game_id):
        print(f"  [OK] Game {game_id} already in database")
        return True

    print(f"  [FETCH] Game {game_id} not in database, fetching from API...")
    try:
        load_game_data(game_id)
        print(f"  [OK] Game {game_id} loaded successfully")
        return True
    except Exception as e:
        print(f"  [ERROR] Error loading game {game_id}: {e}")
        return False


def get_game_analysis(game_id):
    """
    Get complete game analysis from database

    Args:
        game_id: Game ID to analyze

    Returns:
        Dict with game analysis in same format as old game_analysis.py
    """
    session = Session()
    try:
        # Get game
        game = session.query(Game).filter(Game.game_id == game_id).first()
        if not game:
            return None

        # Get teams
        home_team = session.query(Team).filter(Team.team_id == game.home_team_id).first()
        away_team = session.query(Team).filter(Team.team_id == game.away_team_id).first()

        # Determine winner
        if game.home_score > game.away_score:
            winner = home_team.team_code
            loser = away_team.team_code
        else:
            winner = away_team.team_code
            loser = home_team.team_code

        # Fetch venue from API
        venue = 'Unknown'
        is_takeover = False
        takeover_city = None

        try:
            from fetch_data import fetch_game_summary
            api_data = fetch_game_summary(game_id)
            if 'GC' in api_data and 'Gamesummary' in api_data['GC']:
                venue = api_data['GC']['Gamesummary'].get('venue', 'Unknown')

                # Check if this is a takeover game
                venue_name = venue.split('|')[0].strip() if '|' in venue else venue.strip()
                is_home_venue = any(home_venue.lower() in venue_name.lower()
                                   for home_venue in PWHL_HOME_VENUES)

                if not is_home_venue:
                    is_takeover = True
                    # Extract city from venue
                    if '|' in venue:
                        location = venue.split('|')[1].strip()
                        takeover_city = location.split(',')[0].strip()
        except:
            pass  # Silently fail if API call fails

        # Game info
        game_info = {
            'game_id': str(game.game_id),
            'date': game.date.strftime('%Y-%m-%d'),
            'home_team': home_team.team_code,
            'visitor_team': away_team.team_code,
            'home_score': game.home_score,
            'visitor_score': game.away_score,
            'final_score': f"{game.away_score}-{game.home_score}",
            'venue': venue,
            'attendance': game.attendance if game.attendance else 'N/A',
            'winner': winner,
            'loser': loser,
            'is_takeover': is_takeover,
            'takeover_city': takeover_city
        }

        # Get hot players (players with strong performances)
        hot_players = []

        player_stats = session.query(PlayerGameStats, Player).join(
            Player, PlayerGameStats.player_id == Player.player_id
        ).filter(
            PlayerGameStats.game_id == game_id
        ).all()

        for stats, player in player_stats:
            # Hot player criteria (same as old logic)
            is_hot = False
            highlights = []

            # Multi-goal or multi-point game
            if stats.goals >= 2:
                highlights.append(f"{stats.goals}G")
                is_hot = True
            elif stats.goals == 1:
                highlights.append(f"{stats.goals}G")

            if stats.assists >= 2:
                highlights.append(f"{stats.assists}A")
                is_hot = True
            elif stats.assists == 1:
                highlights.append(f"{stats.assists}A")

            if stats.points >= 3:
                is_hot = True

            # High shot volume
            if stats.shots >= 6:
                highlights.append(f"{stats.shots} shots")
                is_hot = True

            # Strong plus/minus
            if stats.plus_minus >= 3:
                highlights.append(f"+{stats.plus_minus}")
                is_hot = True
            elif stats.plus_minus <= -3:
                highlights.append(f"{stats.plus_minus}")

            if is_hot:
                # Get team code
                team = session.query(Team).filter(Team.team_id == stats.team_id).first()

                hot_players.append({
                    'name': f"{player.first_name} {player.last_name}",
                    'jersey': player.jersey_number if player.jersey_number else '?',
                    'position': player.position,
                    'goals': stats.goals,
                    'assists': stats.assists,
                    'points': stats.points,
                    'plus_minus': str(stats.plus_minus) if stats.plus_minus >= 0 else str(stats.plus_minus),
                    'shots': stats.shots,
                    'highlights': highlights,
                    'team': team.team_code if team else 'UNK'
                })

        # Sort by points
        hot_players.sort(key=lambda x: x['points'], reverse=True)

        # Get hot goalies
        hot_goalies = []

        goalie_stats = session.query(GoalieGameStats, Player).join(
            Player, GoalieGameStats.player_id == Player.player_id
        ).filter(
            GoalieGameStats.game_id == game_id
        ).all()

        for stats, player in goalie_stats:
            is_hot = False
            highlights = []

            # High save count
            if stats.saves >= 30:
                highlights.append(f"{stats.saves} saves")
                is_hot = True

            # Elite save percentage
            if stats.shots_against >= 20 and stats.save_percentage and stats.save_percentage >= 0.95:
                highlights.append(f"{stats.save_percentage*100:.1f}% SV%")
                is_hot = True

            # Shutout
            if stats.goals_against == 0 and stats.shots_against >= 15:
                highlights.append("SHUTOUT")
                is_hot = True

            if is_hot:
                team = session.query(Team).filter(Team.team_id == stats.team_id).first()

                hot_goalies.append({
                    'name': f"{player.first_name} {player.last_name}",
                    'jersey': player.jersey_number if player.jersey_number else '?',
                    'position': 'G',
                    'saves': stats.saves,
                    'shots_against': stats.shots_against,
                    'goals_against': stats.goals_against,
                    'save_pct': stats.save_percentage * 100 if stats.save_percentage else 0,
                    'time': f"{stats.minutes_played}:00",
                    'highlights': highlights,
                    'team': team.team_code if team else 'UNK'
                })

        # Detect historical firsts
        firsts = get_all_firsts_for_game(game_id)

        return {
            'game_info': game_info,
            'hot_players': hot_players,
            'hot_goalies': hot_goalies,
            'period_analysis': {},  # Not stored in current DB schema
            'mvps': [],  # Not stored in current DB schema
            'firsts': firsts  # Historical achievements
        }

    finally:
        session.close()


def get_recent_games(days_back=7):
    """
    Get recent completed games from database

    Args:
        days_back: Number of days to look back

    Returns:
        List of game dicts
    """
    session = Session()
    try:
        cutoff_date = datetime.now().date() - timedelta(days=days_back)

        games = session.query(Game).filter(
            Game.game_status == 'final',
            Game.date >= cutoff_date
        ).order_by(desc(Game.date)).all()

        result = []
        for game in games:
            home_team = session.query(Team).filter(Team.team_id == game.home_team_id).first()
            away_team = session.query(Team).filter(Team.team_id == game.away_team_id).first()

            result.append({
                'game_id': game.game_id,
                'date': game.date.strftime('%Y-%m-%d'),
                'home_team': home_team.team_code if home_team else 'UNK',
                'visitor_team': away_team.team_code if away_team else 'UNK',
                'home_score': game.home_score,
                'visitor_score': game.away_score
            })

        return result

    finally:
        session.close()
