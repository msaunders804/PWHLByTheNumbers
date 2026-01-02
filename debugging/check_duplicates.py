#!/usr/bin/env python3
"""
Check for duplicate game stats in database
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
from db_models import Player, PlayerGameStats, Game

# Database configuration
DATABASE_URL = 'postgresql://postgres:SecurePassword@localhost/pwhl_analytics'
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

session = Session()

print("Checking for duplicate player game stats...")
print("=" * 80)

# Find Marie Philip Poulin
marie = session.query(Player).filter(
    Player.last_name.ilike('%poulin%'),
    Player.first_name.ilike('%marie%')
).first()

if marie:
    print(f"Player: {marie.first_name} {marie.last_name} (ID: {marie.player_id})")

    # Check for duplicate records for the same game
    duplicates = session.query(
        PlayerGameStats.game_id,
        func.count(PlayerGameStats.id).label('count')
    ).filter(
        PlayerGameStats.player_id == marie.player_id
    ).group_by(
        PlayerGameStats.game_id
    ).having(
        func.count(PlayerGameStats.id) > 1
    ).all()

    if duplicates:
        print(f"\n⚠️  Found {len(duplicates)} games with duplicate stats:")
        for dup in duplicates[:10]:  # Show first 10
            print(f"  Game {dup.game_id}: {dup.count} duplicate records")
    else:
        print("\n✓ No duplicate stats found")

    # Show sample game stats
    print(f"\nSample game stats for {marie.first_name} {marie.last_name}:")
    print("-" * 80)

    sample_stats = session.query(
        PlayerGameStats, Game
    ).join(
        Game, PlayerGameStats.game_id == Game.game_id
    ).filter(
        PlayerGameStats.player_id == marie.player_id
    ).order_by(
        Game.date.desc()
    ).limit(5).all()

    print(f"{'Game ID':<10} {'Date':<12} {'G':<5} {'A':<5} {'PTS':<5}")
    print("-" * 80)
    for stat, game in sample_stats:
        print(f"{stat.game_id:<10} {game.date.strftime('%Y-%m-%d'):<12} {stat.goals:<5} {stat.assists:<5} {stat.points:<5}")

    # Total records
    total_records = session.query(PlayerGameStats).filter(
        PlayerGameStats.player_id == marie.player_id
    ).count()

    unique_games = session.query(
        func.count(func.distinct(PlayerGameStats.game_id))
    ).filter(
        PlayerGameStats.player_id == marie.player_id
    ).scalar()

    print(f"\nTotal stat records: {total_records}")
    print(f"Unique games played: {unique_games}")

    if total_records > unique_games:
        print(f"⚠️  PROBLEM: {total_records - unique_games} duplicate records!")

session.close()
