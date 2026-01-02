#!/usr/bin/env python3
"""
Career Statistics Calculator
Functions to calculate and retrieve career statistics for PWHL players
"""

import sys
import os

# Add pwhl_analytics_db to path
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)  # Go up one level
db_path = os.path.join(parent_dir, 'pwhl_analytics_db')
sys.path.insert(0, db_path)

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from db_models import Player, PlayerGameStats, GoalieGameStats, Game, Team

# Database configuration
DATABASE_URL = 'postgresql://postgres:SecurePassword@localhost/pwhl_analytics'
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


def get_career_leaders(stat='points', limit=10, season_id=None):
    """
    Get top players by career stat

    Args:
        stat: Stat to rank by ('points', 'goals', 'assists', 'games')
        limit: Number of players to return
        season_id: Optional - filter to specific season

    Returns:
        List of dicts with player career stats
    """
    session = Session()

    try:
        # Build query
        query = session.query(
            Player.player_id,
            Player.first_name,
            Player.last_name,
            Player.position,
            Player.jersey_number,
            func.count(func.distinct(PlayerGameStats.game_id)).label('games_played'),
            func.sum(PlayerGameStats.goals).label('goals'),
            func.sum(PlayerGameStats.assists).label('assists'),
            func.sum(PlayerGameStats.points).label('points'),
            func.sum(PlayerGameStats.shots).label('shots'),
            func.sum(PlayerGameStats.pim).label('pim')
        ).join(
            PlayerGameStats, Player.player_id == PlayerGameStats.player_id
        )

        # Filter by season if specified
        if season_id:
            query = query.join(
                Game, PlayerGameStats.game_id == Game.game_id
            ).filter(Game.season_id == season_id)

        # Group by player
        query = query.group_by(
            Player.player_id,
            Player.first_name,
            Player.last_name,
            Player.position,
            Player.jersey_number
        )

        # Order by requested stat
        if stat == 'points':
            query = query.order_by(func.sum(PlayerGameStats.points).desc())
        elif stat == 'goals':
            query = query.order_by(func.sum(PlayerGameStats.goals).desc())
        elif stat == 'assists':
            query = query.order_by(func.sum(PlayerGameStats.assists).desc())
        elif stat == 'games':
            query = query.order_by(func.count(func.distinct(PlayerGameStats.game_id)).desc())

        # Limit results
        query = query.limit(limit)

        # Execute query
        results = query.all()

        # Format results
        leaders = []
        for row in results:
            ppg = round(row.points / row.games_played, 2) if row.games_played > 0 else 0
            shoot_pct = round((row.goals / row.shots) * 100, 1) if row.shots > 0 else 0

            leaders.append({
                'player_id': row.player_id,
                'name': f"{row.first_name} {row.last_name}",
                'position': row.position,
                'jersey': row.jersey_number or '?',
                'games_played': row.games_played,
                'goals': row.goals,
                'assists': row.assists,
                'points': row.points,
                'shots': row.shots,
                'pim': row.pim,
                'ppg': ppg,
                'shooting_pct': shoot_pct
            })

        return leaders

    finally:
        session.close()


def get_goalie_leaders(limit=10, season_id=None):
    """
    Get top goalies by save percentage

    Args:
        limit: Number of goalies to return
        season_id: Optional - filter to specific season

    Returns:
        List of dicts with goalie career stats
    """
    session = Session()

    try:
        # Build query
        query = session.query(
            Player.player_id,
            Player.first_name,
            Player.last_name,
            Player.position,
            Player.jersey_number,
            func.count(func.distinct(GoalieGameStats.game_id)).label('games_played'),
            func.sum(GoalieGameStats.shots_against).label('shots_against'),
            func.sum(GoalieGameStats.saves).label('saves'),
            func.sum(GoalieGameStats.goals_against).label('goals_against'),
            func.sum(GoalieGameStats.minutes_played).label('minutes')
        ).join(
            GoalieGameStats, Player.player_id == GoalieGameStats.player_id
        )

        # Filter by season if specified
        if season_id:
            query = query.join(
                Game, GoalieGameStats.game_id == Game.game_id
            ).filter(Game.season_id == season_id)

        # Group by player
        query = query.group_by(
            Player.player_id,
            Player.first_name,
            Player.last_name,
            Player.position,
            Player.jersey_number
        )

        # Filter for goalies with meaningful playing time
        query = query.having(func.sum(GoalieGameStats.shots_against) >= 50)

        # Order by save percentage (calculated)
        # Multiply by 1.0 to convert to float instead of using .cast()
        query = query.order_by(
            (func.sum(GoalieGameStats.saves) * 1.0 /
             func.nullif(func.sum(GoalieGameStats.shots_against), 0)).desc()
        )

        # Limit results
        query = query.limit(limit)

        # Execute query
        results = query.all()

        # Format results
        leaders = []
        for row in results:
            sv_pct = round(row.saves / row.shots_against, 4) if row.shots_against > 0 else 0
            gaa = round((row.goals_against / row.minutes) * 60, 2) if row.minutes > 0 else 0

            # Count shutouts
            shutouts = session.query(GoalieGameStats).filter(
                GoalieGameStats.player_id == row.player_id,
                GoalieGameStats.goals_against == 0,
                GoalieGameStats.shots_against >= 15
            ).count()

            leaders.append({
                'player_id': row.player_id,
                'name': f"{row.first_name} {row.last_name}",
                'position': row.position,
                'jersey': row.jersey_number or '?',
                'games_played': row.games_played,
                'shots_against': row.shots_against,
                'saves': row.saves,
                'goals_against': row.goals_against,
                'save_pct': sv_pct,
                'gaa': gaa,
                'shutouts': shutouts
            })

        return leaders

    finally:
        session.close()


def print_career_leaders(stat='points', limit=10, season_id=None):
    """Print career leaders table"""
    leaders = get_career_leaders(stat, limit, season_id)

    season_text = f"Season {season_id}" if season_id else "Career"
    print(f"\n{season_text} Leaders - {stat.upper()}")
    print("=" * 90)
    print(f"{'RK':<4} {'PLAYER':<25} {'POS':<5} {'GP':<5} {'G':<5} {'A':<5} {'PTS':<5} {'PPG':<6} {'SH%':<6}")
    print("-" * 90)

    for idx, player in enumerate(leaders, 1):
        print(f"{idx:<4} {player['name']:<25} {player['position']:<5} "
              f"{player['games_played']:<5} {player['goals']:<5} {player['assists']:<5} "
              f"{player['points']:<5} {player['ppg']:<6.2f} {player['shooting_pct']:<6.1f}")

    print("-" * 90)


def print_goalie_leaders(limit=10, season_id=None):
    """Print goalie leaders table"""
    leaders = get_goalie_leaders(limit, season_id)

    season_text = f"Season {season_id}" if season_id else "Career"
    print(f"\n{season_text} Goalie Leaders - SAVE PERCENTAGE")
    print("=" * 90)
    print(f"{'RK':<4} {'GOALIE':<25} {'GP':<5} {'SA':<6} {'SV':<6} {'GA':<5} {'SV%':<7} {'GAA':<6} {'SO':<4}")
    print("-" * 90)

    for idx, goalie in enumerate(leaders, 1):
        print(f"{idx:<4} {goalie['name']:<25} {goalie['games_played']:<5} "
              f"{goalie['shots_against']:<6} {goalie['saves']:<6} {goalie['goals_against']:<5} "
              f"{goalie['save_pct']:<7.3f} {goalie['gaa']:<6.2f} {goalie['shutouts']:<4}")

    print("-" * 90)


if __name__ == "__main__":
    print("=" * 60)
    print("PWHL CAREER STATISTICS")
    print("=" * 60)

    # Career leaders
    print_career_leaders('points', 10)
    print_career_leaders('goals', 10)
    print_goalie_leaders(10)

    # Current season leaders (season 8)
    print("\n\n")
    print("=" * 60)
    print("CURRENT SEASON STATISTICS (Season 8)")
    print("=" * 60)
    print_career_leaders('points', 10, season_id=8)
    print_goalie_leaders(10, season_id=8)
