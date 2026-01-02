#!/usr/bin/env python3
"""
Debug script to check what's in the database
"""

import sys
import os

# Add pwhl_analytics_db to path
script_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(script_dir, 'pwhl_analytics_db')
sys.path.insert(0, db_path)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db_models import Game, Team

# Database configuration
DATABASE_URL = 'postgresql://postgres:SecurePassword@localhost/pwhl_analytics'
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

session = Session()

# Check teams for season 8
print("Teams in season 8:")
teams = session.query(Team).filter(Team.season_id == 8).all()
for team in teams:
    print(f"  {team.team_code}: {team.team_name} (ID: {team.team_id})")

print(f"\nTotal teams: {len(teams)}")

# Check games for season 8
print("\nGames in season 8:")
games = session.query(Game).filter(Game.season_id == 8).all()
print(f"Total games: {len(games)}")

completed_games = session.query(Game).filter(
    Game.season_id == 8,
    Game.game_status == 'final'
).all()
print(f"Completed games: {len(completed_games)}")

if completed_games:
    print("\nSample completed games:")
    for game in completed_games[:5]:
        home_team = session.query(Team).filter(Team.team_id == game.home_team_id).first()
        away_team = session.query(Team).filter(Team.team_id == game.away_team_id).first()

        print(f"  Game {game.game_id}: {away_team.team_code if away_team else '?'} @ "
              f"{home_team.team_code if home_team else '?'} = "
              f"{game.away_score}-{game.home_score} (Status: {game.game_status})")

session.close()
