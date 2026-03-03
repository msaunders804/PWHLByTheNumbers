"""
PWHL Analytics - SQLAlchemy Models (MySQL)
All String columns have explicit lengths required by MySQL.
"""

from sqlalchemy import Column, Integer, String, Date, Float, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Game(Base):
    __tablename__ = 'games'

    game_id           = Column(Integer, primary_key=True)
    season_id         = Column(Integer, nullable=False)
    date              = Column(Date, nullable=False)
    home_team_id      = Column(Integer, ForeignKey('teams.team_id'), nullable=False)
    away_team_id      = Column(Integer, ForeignKey('teams.team_id'), nullable=False)
    home_score        = Column(Integer)
    away_score        = Column(Integer)
    game_status       = Column(String(20))
    result_type       = Column(String(3))           # 'REG', 'OT', 'SO'
    overtime_periods  = Column(Integer, default=0)
    attendance        = Column(Integer, nullable=True)
    venue             = Column(String(100), nullable=True)

    home_team = relationship('Team', foreign_keys=[home_team_id])
    away_team = relationship('Team', foreign_keys=[away_team_id])


class Team(Base):
    __tablename__ = 'teams'

    team_id   = Column(Integer, primary_key=True)
    team_name = Column(String(100), nullable=False)
    team_code = Column(String(10),  nullable=False)
    season_id = Column(Integer,     nullable=False)


class Player(Base):
    __tablename__ = 'players'

    player_id         = Column(Integer, primary_key=True)
    first_name        = Column(String(100), nullable=False)
    last_name         = Column(String(100), nullable=False)
    position          = Column(String(5),   nullable=True)
    jersey_number     = Column(Integer,     nullable=True)
    avg_toi_seconds   = Column(Integer,     nullable=True)   # seconds, from statviewtype
    nationality       = Column(String(100), nullable=True)   # birthcntry
    hometown          = Column(String(200), nullable=True)
    height            = Column(String(10),  nullable=True)
    shoots            = Column(String(1),   nullable=True)


class PlayerGameStats(Base):
    __tablename__ = 'player_game_stats'

    id          = Column(Integer, primary_key=True, autoincrement=True)
    game_id     = Column(Integer, ForeignKey('games.game_id'),    nullable=False)
    player_id   = Column(Integer, ForeignKey('players.player_id'), nullable=False)
    team_id     = Column(Integer, ForeignKey('teams.team_id'),    nullable=False)
    goals       = Column(Integer, default=0)
    assists     = Column(Integer, default=0)
    points      = Column(Integer, default=0)
    shots       = Column(Integer, default=0)
    plus_minus  = Column(Integer, default=0)
    pim         = Column(Integer, default=0)
    toi_seconds = Column(Integer, default=None)


class GoalieGameStats(Base):
    __tablename__ = 'goalie_game_stats'

    id              = Column(Integer, primary_key=True, autoincrement=True)
    game_id         = Column(Integer, ForeignKey('games.game_id'),    nullable=False)
    player_id       = Column(Integer, ForeignKey('players.player_id'), nullable=False)
    team_id         = Column(Integer, ForeignKey('teams.team_id'),    nullable=False)
    shots_against   = Column(Integer, default=0)
    saves           = Column(Integer, default=0)
    goals_against   = Column(Integer, default=0)
    save_percentage = Column(Float,   nullable=True)
    minutes_played  = Column(Integer, default=0)   # stored as seconds
    decision        = Column(String(5), nullable=True)  # 'W', 'L', 'OTL', 'SOL'
