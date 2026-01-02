from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db_models import Game, Team, Player, PlayerGameStats, GoalieGameStats
from fetch_data import fetch_season_schedule, fetch_game_summary, fetch_teams
from datetime import datetime

DATABASE_URL = 'postgresql://postgres:SecurePassword@localhost/pwhl_analytics'
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

def load_teams(season_id=8):
    """Load all teams for a season"""
    session = Session()
    try:
        teams_data = fetch_teams(season_id)
        for team_data in teams_data['SiteKit']['Teamsbyseason']:
            team = Team(
                team_id=int(team_data['id']),
                team_name=team_data['name'],
                team_code=team_data['code'],
                season_id=season_id
            )
            session.merge(team)
        session.commit()
        print(f"✓ Loaded {len(teams_data['SiteKit']['Teamsbyseason'])} teams for season {season_id}")
    except Exception as e:
        session.rollback()
        print(f"✗ Error loading teams: {e}")
        raise
    finally:
        session.close()

def load_game_data(game_id, session=None):
    """Load a single game's complete data into database"""
    close_session = False
    if session is None:
        session = Session()
        close_session = True
    
    try:
        data = fetch_game_summary(game_id)
        summary = data['GC']['Gamesummary']
        meta = summary['meta']
        
        # Insert/update game
        game = Game(
            game_id=int(meta['id']),
            season_id=int(meta['season_id']),
            date=datetime.strptime(meta['date_played'], '%Y-%m-%d').date(),
            home_team_id=int(meta['home_team']),
            away_team_id=int(meta['visiting_team']),
            home_score=int(meta['home_goal_count']),
            away_score=int(meta['visiting_goal_count']),
            game_status='final' if meta['final'] == '1' else 'in_progress',
            attendance=int(meta['attendance']) if meta['attendance'] else None,
            venue=summary.get('venue', None)
        )
        session.merge(game)

        # Delete existing stats for this game to prevent duplicates
        session.query(PlayerGameStats).filter(PlayerGameStats.game_id == int(meta['id'])).delete()
        session.query(GoalieGameStats).filter(GoalieGameStats.game_id == int(meta['id'])).delete()

        # Load home team skaters
        for player_data in summary['home_team_lineup']['players']:
            player = Player(
                player_id=int(player_data['player_id']),
                first_name=player_data['first_name'],
                last_name=player_data['last_name'],
                position=player_data['position_str'],
                jersey_number=int(player_data['jersey_number']) if player_data['jersey_number'] else None
            )
            session.merge(player)
            
            stats = PlayerGameStats(
                game_id=int(meta['id']),
                player_id=int(player_data['player_id']),
                team_id=int(meta['home_team']),
                goals=int(player_data['goals']),
                assists=int(player_data['assists']),
                points=int(player_data['goals']) + int(player_data['assists']),
                shots=int(player_data['shots_on']),
                plus_minus=int(player_data['plusminus']),
                pim=int(player_data['pim'])
            )
            session.add(stats)
        
        # Load visitor team skaters
        for player_data in summary['visitor_team_lineup']['players']:
            player = Player(
                player_id=int(player_data['player_id']),
                first_name=player_data['first_name'],
                last_name=player_data['last_name'],
                position=player_data['position_str'],
                jersey_number=int(player_data['jersey_number']) if player_data['jersey_number'] else None
            )
            session.merge(player)
            
            stats = PlayerGameStats(
                game_id=int(meta['id']),
                player_id=int(player_data['player_id']),
                team_id=int(meta['visiting_team']),
                goals=int(player_data['goals']),
                assists=int(player_data['assists']),
                points=int(player_data['goals']) + int(player_data['assists']),
                shots=int(player_data['shots_on']),
                plus_minus=int(player_data['plusminus']),
                pim=int(player_data['pim'])
            )
            session.add(stats)
        
        # Load goalies (aggregated across periods)
        goalie_stats = {}
        
        # Process home goalies
        for goalie_data in summary['home_team_lineup']['goalies']:
            pid = int(goalie_data['player_id'])
            if pid not in goalie_stats:
                goalie_stats[pid] = {
                    'player_id': pid,
                    'team_id': int(meta['home_team']),
                    'first_name': goalie_data['first_name'],
                    'last_name': goalie_data['last_name'],
                    'shots_against': 0,
                    'saves': 0,
                    'goals_against': 0,
                    'minutes_played': 0
                }
            goalie_stats[pid]['shots_against'] += int(goalie_data['shots_against'])
            goalie_stats[pid]['saves'] += int(goalie_data['saves'])
            goalie_stats[pid]['goals_against'] += int(goalie_data['goals_against'])
            goalie_stats[pid]['minutes_played'] += int(goalie_data['seconds']) // 60
        
        # Process visitor goalies
        for goalie_data in summary['visitor_team_lineup']['goalies']:
            pid = int(goalie_data['player_id'])
            if pid not in goalie_stats:
                goalie_stats[pid] = {
                    'player_id': pid,
                    'team_id': int(meta['visiting_team']),
                    'first_name': goalie_data['first_name'],
                    'last_name': goalie_data['last_name'],
                    'shots_against': 0,
                    'saves': 0,
                    'goals_against': 0,
                    'minutes_played': 0
                }
            goalie_stats[pid]['shots_against'] += int(goalie_data['shots_against'])
            goalie_stats[pid]['saves'] += int(goalie_data['saves'])
            goalie_stats[pid]['goals_against'] += int(goalie_data['goals_against'])
            goalie_stats[pid]['minutes_played'] += int(goalie_data['seconds']) // 60
        
        # First merge all goalie players
        for pid, gstats in goalie_stats.items():
            player = Player(
                player_id=gstats['player_id'],
                first_name=gstats['first_name'],
                last_name=gstats['last_name'],
                position='G',
                jersey_number=None
            )
            session.merge(player)
        
        # Flush to ensure players exist before adding stats
        session.flush()
        
        # Now add goalie stats
        for pid, gstats in goalie_stats.items():
            save_pct = None
            if gstats['shots_against'] > 0:
                save_pct = gstats['saves'] / gstats['shots_against']
            
            goalie_stat = GoalieGameStats(
                game_id=int(meta['id']),
                player_id=gstats['player_id'],
                team_id=gstats['team_id'],
                shots_against=gstats['shots_against'],
                saves=gstats['saves'],
                goals_against=gstats['goals_against'],
                save_percentage=save_pct,
                minutes_played=gstats['minutes_played']
            )
            session.add(goalie_stat)
        
        if close_session:
            session.commit()
            print(f"✓ Loaded game {game_id}")
        
    except Exception as e:
        if close_session:
            session.rollback()
        print(f"✗ Error loading game {game_id}: {e}")
        raise
    finally:
        if close_session:
            session.close()

def backfill_all_seasons():
    """Backfill all PWHL seasons"""
    from fetch_data import fetch_season_schedule
    
    # Fetch seasons to get all season IDs
    import requests
    BASE_URL = "https://lscluster.hockeytech.com/feed/index.php"
    PARAMS = {
        "key": "446521baf8c38984",
        "client_code": "pwhl",
        "feed": "modulekit",
        "view": "seasons"
    }
    
    response = requests.get(BASE_URL, params=PARAMS)
    seasons_data = response.json()
    
    # Get all season IDs
    seasons = seasons_data['SiteKit']['Seasons']
    print(f"Found {len(seasons)} seasons to backfill\n")
    
    for season in seasons:
        season_id = int(season['season_id'])
        season_name = season['season_name']
        
        print(f"\n{'='*60}")
        print(f"SEASON: {season_name} (ID: {season_id})")
        print(f"{'='*60}")
        
        try:
            # Load teams for this season
            load_teams(season_id)
            
            # Get schedule
            schedule_data = fetch_season_schedule(season_id)
            games = schedule_data['SiteKit']['Schedule']
            completed_games = [g for g in games if g['game_status'] == 'Final']
            
            print(f"Found {len(completed_games)} completed games")
            
            # Load each game
            for i, game in enumerate(completed_games, 1):
                print(f"[{i}/{len(completed_games)}] ", end="")
                try:
                    load_game_data(game['id'])
                except Exception as e:
                    print(f"  Skipping - error: {e}")
                    continue
            
            print(f"✓ Completed season {season_name}")
            
        except Exception as e:
            print(f"✗ Error processing season {season_name}: {e}")
            continue
    
    print(f"\n{'='*60}")
    print("BACKFILL COMPLETE!")
    print(f"{'='*60}")

if __name__ == "__main__":
    session = Session()
    
    try:
        print("Testing with season 8, game 210...")
        teams_data = fetch_teams(8)
        for team_data in teams_data['SiteKit']['Teamsbyseason']:
            team = Team(
                team_id=int(team_data['id']),
                team_name=team_data['name'],
                team_code=team_data['code'],
                season_id=8
            )
            session.merge(team)
        session.commit()
        print(f"✓ Loaded {len(teams_data['SiteKit']['Teamsbyseason'])} teams")
        
        print("Loading game 210...")
        load_game_data(210, session=session)
        session.commit()
        print("✓ Test successful!")
        
    finally:
        session.close()
    
    print("\n" + "="*60)
    print("Ready to backfill ALL seasons?")
    print("This will load every completed game from PWHL history.")
    print("="*60)
    response = input("Type 'yes' to continue: ")
    
    if response.lower() == 'yes':
        backfill_all_seasons()