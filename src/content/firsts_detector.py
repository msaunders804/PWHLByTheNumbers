"""
Historical Firsts Detector
Analyzes game data against historical records to identify notable "firsts"
"""

import sys
import os

# Add pwhl_analytics_db to path
script_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(script_dir, 'pwhl_analytics_db')
sys.path.insert(0, db_path)

from sqlalchemy import create_engine, func, and_
from sqlalchemy.orm import sessionmaker
from db_models import Game, Team, Player, PlayerGameStats, GoalieGameStats
from datetime import datetime

# Database configuration
DATABASE_URL = 'postgresql://postgres:SecurePassword@localhost/pwhl_analytics'
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


def detect_player_firsts(game_id, player_id, game_stats):
    """
    Detect if this game contains any "firsts" for a player

    Args:
        game_id: Current game ID
        player_id: Player ID to check
        game_stats: Dict with player's stats for this game

    Returns:
        List of "first" achievements as strings
    """
    session = Session()
    firsts = []

    try:
        # Get the game date for season context
        game = session.query(Game).filter(Game.game_id == game_id).first()
        if not game:
            return firsts

        season_id = game.season_id

        # Get player info
        player = session.query(Player).filter(Player.player_id == player_id).first()
        if not player:
            return firsts

        player_name = f"{player.first_name} {player.last_name}"

        # Check for HAT TRICK (3+ goals)
        if game_stats.get('goals', 0) >= 3:
            # Check if this is the FIRST hat trick in the ENTIRE LEAGUE this season
            any_previous_hat_tricks = session.query(PlayerGameStats).join(
                Game, PlayerGameStats.game_id == Game.game_id
            ).filter(
                and_(
                    PlayerGameStats.goals >= 3,
                    Game.season_id == season_id,
                    Game.date < game.date
                )
            ).count()

            if any_previous_hat_tricks == 0:
                # First hat trick by ANYONE in the league this season
                firsts.append({
                    'type': 'first_league_hat_trick',
                    'description': f"FIRST HAT TRICK OF THE SEASON - {player_name} makes history",
                    'detail': f"{game_stats['goals']}-goal performance",
                    'significance': 'high'
                })
            else:
                # Check if this is their personal first hat trick this season
                player_previous_hat_tricks = session.query(PlayerGameStats).join(
                    Game, PlayerGameStats.game_id == Game.game_id
                ).filter(
                    and_(
                        PlayerGameStats.player_id == player_id,
                        PlayerGameStats.goals >= 3,
                        Game.season_id == season_id,
                        Game.date < game.date
                    )
                ).count()

                if player_previous_hat_tricks == 0:
                    firsts.append({
                        'type': 'hat_trick',
                        'description': f"First hat trick of the season for {player_name}",
                        'detail': f"{game_stats['goals']}-goal performance",
                        'significance': 'high'
                    })

        # Check for 4+ POINT GAME
        if game_stats.get('points', 0) >= 4:
            # Check if this is their first 4+ point game this season
            previous_4pt_games = session.query(PlayerGameStats).join(
                Game, PlayerGameStats.game_id == Game.game_id
            ).filter(
                and_(
                    PlayerGameStats.player_id == player_id,
                    PlayerGameStats.points >= 4,
                    Game.season_id == season_id,
                    Game.game_id < game_id,
                    Game.date < game.date
                )
            ).count()

            if previous_4pt_games == 0:
                firsts.append({
                    'type': 'multi_point',
                    'description': f"First {game_stats['points']}-point game of the season for {player_name}",
                    'detail': f"{game_stats['goals']}G, {game_stats['assists']}A",
                    'significance': 'medium'
                })

        # Check for FIRST GOAL of season
        if game_stats.get('goals', 0) >= 1:
            previous_goals = session.query(func.sum(PlayerGameStats.goals)).join(
                Game, PlayerGameStats.game_id == Game.game_id
            ).filter(
                and_(
                    PlayerGameStats.player_id == player_id,
                    Game.season_id == season_id,
                    Game.game_id < game_id,
                    Game.date < game.date
                )
            ).scalar() or 0

            if previous_goals == 0:
                firsts.append({
                    'type': 'first_goal',
                    'description': f"First goal of the season for {player_name}",
                    'detail': f"Scored {game_stats['goals']} goal(s)",
                    'significance': 'medium'
                })

        # Check for FIRST POINT of season
        if game_stats.get('points', 0) >= 1:
            previous_points = session.query(func.sum(PlayerGameStats.points)).join(
                Game, PlayerGameStats.game_id == Game.game_id
            ).filter(
                and_(
                    PlayerGameStats.player_id == player_id,
                    Game.season_id == season_id,
                    Game.game_id < game_id,
                    Game.date < game.date
                )
            ).scalar() or 0

            if previous_points == 0:
                firsts.append({
                    'type': 'first_point',
                    'description': f"First point of the season for {player_name}",
                    'detail': f"{game_stats['goals']}G, {game_stats['assists']}A",
                    'significance': 'low'
                })

        return firsts

    finally:
        session.close()


def detect_goalie_firsts(game_id, player_id, goalie_stats):
    """
    Detect if this game contains any "firsts" for a goalie

    Args:
        game_id: Current game ID
        player_id: Goalie ID to check
        goalie_stats: Dict with goalie's stats for this game

    Returns:
        List of "first" achievements as strings
    """
    session = Session()
    firsts = []

    try:
        # Get the game date for season context
        game = session.query(Game).filter(Game.game_id == game_id).first()
        if not game:
            return firsts

        season_id = game.season_id

        # Get player info
        player = session.query(Player).filter(Player.player_id == player_id).first()
        if not player:
            return firsts

        player_name = f"{player.first_name} {player.last_name}"

        # Check for SHUTOUT (0 goals against, 15+ shots)
        if goalie_stats.get('goals_against', 0) == 0 and goalie_stats.get('shots_against', 0) >= 15:
            # Check if this is the FIRST shutout in the ENTIRE LEAGUE this season
            any_previous_shutouts = session.query(GoalieGameStats).join(
                Game, GoalieGameStats.game_id == Game.game_id
            ).filter(
                and_(
                    GoalieGameStats.goals_against == 0,
                    GoalieGameStats.shots_against >= 15,
                    Game.season_id == season_id,
                    Game.date < game.date
                )
            ).count()

            if any_previous_shutouts == 0:
                # First shutout by ANYONE in the league this season
                firsts.append({
                    'type': 'first_league_shutout',
                    'description': f"FIRST SHUTOUT OF THE SEASON - {player_name} makes history",
                    'detail': f"{goalie_stats['saves']} saves on {goalie_stats['shots_against']} shots",
                    'significance': 'high'
                })
            else:
                # Check if this is their personal first shutout this season
                player_previous_shutouts = session.query(GoalieGameStats).join(
                    Game, GoalieGameStats.game_id == Game.game_id
                ).filter(
                    and_(
                        GoalieGameStats.player_id == player_id,
                        GoalieGameStats.goals_against == 0,
                        GoalieGameStats.shots_against >= 15,
                        Game.season_id == season_id,
                        Game.date < game.date
                    )
                ).count()

                if player_previous_shutouts == 0:
                    firsts.append({
                        'type': 'shutout',
                        'description': f"First shutout of the season for {player_name}",
                        'detail': f"{goalie_stats['saves']} saves on {goalie_stats['shots_against']} shots",
                        'significance': 'high'
                    })

        # Check for 40+ SAVE GAME
        if goalie_stats.get('saves', 0) >= 40:
            # Check if this is their first 40+ save game this season
            previous_40save_games = session.query(GoalieGameStats).join(
                Game, GoalieGameStats.game_id == Game.game_id
            ).filter(
                and_(
                    GoalieGameStats.player_id == player_id,
                    GoalieGameStats.saves >= 40,
                    Game.season_id == season_id,
                    Game.game_id < game_id,
                    Game.date < game.date
                )
            ).count()

            if previous_40save_games == 0:
                firsts.append({
                    'type': 'high_saves',
                    'description': f"First 40+ save game of the season for {player_name}",
                    'detail': f"{goalie_stats['saves']} saves ({goalie_stats.get('save_pct', 0)*100:.1f}%)",
                    'significance': 'medium'
                })

        # Check for FIRST WIN of season (if team won and goalie played majority)
        if goalie_stats.get('minutes_played', 0) >= 30:
            # Determine if goalie's team won
            team_id = goalie_stats.get('team_id')
            if team_id == game.home_team_id and game.home_score > game.away_score:
                is_win = True
            elif team_id == game.away_team_id and game.away_score > game.home_score:
                is_win = True
            else:
                is_win = False

            if is_win:
                # Count previous wins this season
                # This is complex - need to check games where goalie played and team won
                previous_win_games = session.query(GoalieGameStats).join(
                    Game, GoalieGameStats.game_id == Game.game_id
                ).filter(
                    and_(
                        GoalieGameStats.player_id == player_id,
                        GoalieGameStats.minutes_played >= 30,
                        Game.season_id == season_id,
                        Game.game_id < game_id,
                        Game.date < game.date,
                        # Team won
                        ((GoalieGameStats.team_id == Game.home_team_id) & (Game.home_score > Game.away_score)) |
                        ((GoalieGameStats.team_id == Game.away_team_id) & (Game.away_score > Game.home_score))
                    )
                ).count()

                if previous_win_games == 0:
                    firsts.append({
                        'type': 'first_win',
                        'description': f"First win of the season for {player_name}",
                        'detail': f"{goalie_stats['saves']} saves in the victory",
                        'significance': 'medium'
                    })

        return firsts

    finally:
        session.close()


def detect_team_firsts(game_id):
    """
    Detect team-level firsts (like first win, first shutout, etc.)

    Args:
        game_id: Game ID to check

    Returns:
        Dict with home and away team firsts
    """
    session = Session()
    result = {'home': [], 'away': []}

    try:
        # Get the game
        game = session.query(Game).filter(Game.game_id == game_id).first()
        if not game:
            return result

        season_id = game.season_id

        # Get team info
        home_team = session.query(Team).filter(Team.team_id == game.home_team_id).first()
        away_team = session.query(Team).filter(Team.team_id == game.away_team_id).first()

        # Check home team firsts
        if game.home_score > game.away_score:
            # Home team won - check if first win
            previous_wins = session.query(Game).filter(
                and_(
                    Game.season_id == season_id,
                    Game.game_id < game_id,
                    Game.date < game.date,
                    ((Game.home_team_id == game.home_team_id) & (Game.home_score > Game.away_score)) |
                    ((Game.away_team_id == game.home_team_id) & (Game.away_score > Game.home_score))
                )
            ).count()

            if previous_wins == 0:
                result['home'].append({
                    'type': 'team_first_win',
                    'description': f"First win of the season for {home_team.team_code}",
                    'detail': f"Defeated {away_team.team_code} {game.home_score}-{game.away_score}",
                    'significance': 'high'
                })

        # Check away team firsts
        if game.away_score > game.home_score:
            # Away team won - check if first win
            previous_wins = session.query(Game).filter(
                and_(
                    Game.season_id == season_id,
                    Game.game_id < game_id,
                    Game.date < game.date,
                    ((Game.home_team_id == game.away_team_id) & (Game.home_score > Game.away_score)) |
                    ((Game.away_team_id == game.away_team_id) & (Game.away_score > Game.home_score))
                )
            ).count()

            if previous_wins == 0:
                result['away'].append({
                    'type': 'team_first_win',
                    'description': f"First win of the season for {away_team.team_code}",
                    'detail': f"Defeated {home_team.team_code} {game.away_score}-{game.home_score}",
                    'significance': 'high'
                })

        return result

    finally:
        session.close()


def get_all_firsts_for_game(game_id):
    """
    Get all notable firsts for a specific game

    Args:
        game_id: Game ID to analyze

    Returns:
        Dict with all detected firsts organized by category
    """
    session = Session()

    try:
        firsts = {
            'players': [],
            'goalies': [],
            'teams': {'home': [], 'away': []}
        }

        # Get all player stats for this game
        player_stats = session.query(PlayerGameStats, Player).join(
            Player, PlayerGameStats.player_id == Player.player_id
        ).filter(PlayerGameStats.game_id == game_id).all()

        for stats, player in player_stats:
            game_stats = {
                'goals': stats.goals,
                'assists': stats.assists,
                'points': stats.points,
                'shots': stats.shots,
                'plus_minus': stats.plus_minus,
                'team_id': stats.team_id
            }

            player_firsts = detect_player_firsts(game_id, player.player_id, game_stats)
            if player_firsts:
                for first in player_firsts:
                    first['player_name'] = f"{player.first_name} {player.last_name}"
                    first['player_id'] = player.player_id
                firsts['players'].extend(player_firsts)

        # Get all goalie stats for this game
        goalie_stats = session.query(GoalieGameStats, Player).join(
            Player, GoalieGameStats.player_id == Player.player_id
        ).filter(GoalieGameStats.game_id == game_id).all()

        for stats, player in goalie_stats:
            game_stats = {
                'saves': stats.saves,
                'shots_against': stats.shots_against,
                'goals_against': stats.goals_against,
                'save_pct': stats.save_percentage,
                'minutes_played': stats.minutes_played,
                'team_id': stats.team_id
            }

            goalie_firsts = detect_goalie_firsts(game_id, player.player_id, game_stats)
            if goalie_firsts:
                for first in goalie_firsts:
                    first['player_name'] = f"{player.first_name} {player.last_name}"
                    first['player_id'] = player.player_id
                firsts['goalies'].extend(goalie_firsts)

        # Get team firsts
        team_firsts = detect_team_firsts(game_id)
        firsts['teams'] = team_firsts

        # Sort by significance
        significance_order = {'high': 0, 'medium': 1, 'low': 2}
        firsts['players'].sort(key=lambda x: significance_order.get(x.get('significance', 'low'), 3))
        firsts['goalies'].sort(key=lambda x: significance_order.get(x.get('significance', 'low'), 3))

        return firsts

    finally:
        session.close()


if __name__ == "__main__":
    # Test with a specific game
    import sys

    if len(sys.argv) > 1:
        game_id = int(sys.argv[1])
    else:
        # Use most recent game
        from db_queries import get_most_recent_completed_game
        game_info = get_most_recent_completed_game()
        if game_info:
            game_id = game_info['game_id']
        else:
            print("No games found")
            sys.exit(1)

    print(f"Detecting firsts for Game #{game_id}...")
    print("=" * 60)

    firsts = get_all_firsts_for_game(game_id)

    # Display results
    if firsts['players']:
        print("\n🎯 PLAYER FIRSTS:")
        for first in firsts['players']:
            print(f"  • {first['description']}")
            print(f"    {first['detail']}")

    if firsts['goalies']:
        print("\n🥅 GOALIE FIRSTS:")
        for first in firsts['goalies']:
            print(f"  • {first['description']}")
            print(f"    {first['detail']}")

    if firsts['teams']['home'] or firsts['teams']['away']:
        print("\n🏆 TEAM FIRSTS:")
        for first in firsts['teams']['home'] + firsts['teams']['away']:
            print(f"  • {first['description']}")
            print(f"    {first['detail']}")

    if not (firsts['players'] or firsts['goalies'] or firsts['teams']['home'] or firsts['teams']['away']):
        print("\nNo notable firsts detected for this game.")
