#!/usr/bin/env python3
"""
Debug player statistics to check accuracy
"""

import sys
import os

# Add pwhl_analytics_db to path
script_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(script_dir, 'pwhl_analytics_db')
sys.path.insert(0, db_path)

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from db_models import Player, PlayerGameStats, Game

# Database configuration
DATABASE_URL = 'postgresql://postgres:SecurePassword@localhost/pwhl_analytics'
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

session = Session()

# Check for Marie Philip Poulin
print("Checking Marie Philip Poulin's stats:")
print("=" * 80)

marie = session.query(Player).filter(
    Player.last_name.ilike('%poulin%'),
    Player.first_name.ilike('%marie%')
).first()

if marie:
    print(f"Found: {marie.first_name} {marie.last_name} (ID: {marie.player_id})")

    # Get all her stats
    all_stats = session.query(
        func.count(func.distinct(PlayerGameStats.game_id)).label('gp'),
        func.sum(PlayerGameStats.goals).label('goals'),
        func.sum(PlayerGameStats.assists).label('assists'),
        func.sum(PlayerGameStats.points).label('points')
    ).filter(
        PlayerGameStats.player_id == marie.player_id
    ).first()

    print(f"\nAll-time stats:")
    print(f"  GP: {all_stats.gp}, G: {all_stats.goals}, A: {all_stats.assists}, PTS: {all_stats.points}")

    # Get season 8 stats
    season8_stats = session.query(
        func.count(func.distinct(PlayerGameStats.game_id)).label('gp'),
        func.sum(PlayerGameStats.goals).label('goals'),
        func.sum(PlayerGameStats.assists).label('assists'),
        func.sum(PlayerGameStats.points).label('points')
    ).join(
        Game, PlayerGameStats.game_id == Game.game_id
    ).filter(
        PlayerGameStats.player_id == marie.player_id,
        Game.season_id == 8
    ).first()

    print(f"\nSeason 8 stats:")
    print(f"  GP: {season8_stats.gp}, G: {season8_stats.goals}, A: {season8_stats.assists}, PTS: {season8_stats.points}")

# Check for Daryl Watts
print("\n" + "=" * 80)
print("Checking Daryl Watts' stats:")
print("=" * 80)

watts = session.query(Player).filter(
    Player.last_name.ilike('%watts%')
).first()

if watts:
    print(f"Found: {watts.first_name} {watts.last_name} (ID: {watts.player_id})")

    # Get all stats
    all_stats = session.query(
        func.count(func.distinct(PlayerGameStats.game_id)).label('gp'),
        func.sum(PlayerGameStats.goals).label('goals'),
        func.sum(PlayerGameStats.assists).label('assists'),
        func.sum(PlayerGameStats.points).label('points')
    ).filter(
        PlayerGameStats.player_id == watts.player_id
    ).first()

    print(f"\nAll-time stats:")
    print(f"  GP: {all_stats.gp}, G: {all_stats.goals}, A: {all_stats.assists}, PTS: {all_stats.points}")

    # Get season 8 stats
    season8_stats = session.query(
        func.count(func.distinct(PlayerGameStats.game_id)).label('gp'),
        func.sum(PlayerGameStats.goals).label('goals'),
        func.sum(PlayerGameStats.assists).label('assists'),
        func.sum(PlayerGameStats.points).label('points')
    ).join(
        Game, PlayerGameStats.game_id == Game.game_id
    ).filter(
        PlayerGameStats.player_id == watts.player_id,
        Game.season_id == 8
    ).first()

    print(f"\nSeason 8 stats:")
    print(f"  GP: {season8_stats.gp}, G: {season8_stats.goals}, A: {season8_stats.assists}, PTS: {season8_stats.points}")

# Show top 10 for season 8
print("\n" + "=" * 80)
print("Top 10 Point Scorers - Season 8:")
print("=" * 80)

top_players = session.query(
    Player.first_name,
    Player.last_name,
    func.count(func.distinct(PlayerGameStats.game_id)).label('gp'),
    func.sum(PlayerGameStats.goals).label('goals'),
    func.sum(PlayerGameStats.assists).label('assists'),
    func.sum(PlayerGameStats.points).label('points')
).join(
    PlayerGameStats, Player.player_id == PlayerGameStats.player_id
).join(
    Game, PlayerGameStats.game_id == Game.game_id
).filter(
    Game.season_id == 8
).group_by(
    Player.player_id, Player.first_name, Player.last_name
).order_by(
    func.sum(PlayerGameStats.points).desc()
).limit(10).all()

print(f"{'PLAYER':<30} {'GP':<5} {'G':<5} {'A':<5} {'PTS':<5}")
print("-" * 80)
for p in top_players:
    print(f"{p.first_name} {p.last_name:<28} {p.gp:<5} {p.goals:<5} {p.assists:<5} {p.points:<5}")

session.close()
