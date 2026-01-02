from sqlalchemy import create_engine, Column, Integer, String, Date, Float, ForeignKey
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Game(Base):
    __tablename__ = 'games'

    game_id = Column(Integer, primary_key=True)
    season_id = Column(Integer)
    date = Column(Date)
    home_team_id = Column(Integer, ForeignKey('teams.team_id'))
    away_team_id = Column(Integer, ForeignKey('teams.team_id'))
    home_score = Column(Integer)
    away_score = Column(Integer)
    game_status = Column(String)
    attendance = Column(Integer, nullable=True)
    venue = Column(String, nullable=True)

class Team(Base):
    __tablename__ = 'teams'
    
    team_id = Column(Integer, primary_key=True)
    team_name = Column(String)
    team_code = Column(String)
    season_id = Column(Integer)

class Player(Base):
    __tablename__ = 'players'
    
    player_id = Column(Integer, primary_key=True)
    first_name = Column(String)
    last_name = Column(String)
    position = Column(String)
    jersey_number = Column(Integer, nullable=True)

class PlayerGameStats(Base):
    __tablename__ = 'player_game_stats'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey('games.game_id'))
    player_id = Column(Integer, ForeignKey('players.player_id'))
    team_id = Column(Integer, ForeignKey('teams.team_id'))
    goals = Column(Integer, default=0)
    assists = Column(Integer, default=0)
    points = Column(Integer, default=0)
    shots = Column(Integer, default=0)
    plus_minus = Column(Integer, default=0)
    pim = Column(Integer, default=0)

class GoalieGameStats(Base):
    __tablename__ = 'goalie_game_stats'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey('games.game_id'))
    player_id = Column(Integer, ForeignKey('players.player_id'))
    team_id = Column(Integer, ForeignKey('teams.team_id'))
    shots_against = Column(Integer, default=0)
    saves = Column(Integer, default=0)
    goals_against = Column(Integer, default=0)
    save_percentage = Column(Float, nullable=True)
    minutes_played = Column(Integer, default=0)