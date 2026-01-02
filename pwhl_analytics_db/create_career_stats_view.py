#!/usr/bin/env python3
"""
Create database view for career statistics
This view automatically calculates career totals from game-by-game stats
"""

from sqlalchemy import create_engine, text

# Database configuration
DATABASE_URL = 'postgresql://postgres:SecurePassword@localhost/pwhl_analytics'
engine = create_engine(DATABASE_URL)

# SQL to create career stats view
create_view_sql = """
CREATE OR REPLACE VIEW player_career_stats AS
SELECT
    p.player_id,
    p.first_name,
    p.last_name,
    p.position,
    p.jersey_number,
    COUNT(DISTINCT pgs.game_id) as games_played,
    SUM(pgs.goals) as career_goals,
    SUM(pgs.assists) as career_assists,
    SUM(pgs.points) as career_points,
    SUM(pgs.shots) as career_shots,
    SUM(pgs.pim) as career_pim,
    CASE
        WHEN SUM(pgs.shots) > 0
        THEN ROUND((SUM(pgs.goals)::numeric / SUM(pgs.shots)::numeric) * 100, 2)
        ELSE 0
    END as shooting_percentage,
    ROUND(SUM(pgs.points)::numeric / NULLIF(COUNT(DISTINCT pgs.game_id), 0), 2) as points_per_game
FROM players p
LEFT JOIN player_game_stats pgs ON p.player_id = pgs.player_id
GROUP BY p.player_id, p.first_name, p.last_name, p.position, p.jersey_number
HAVING COUNT(DISTINCT pgs.game_id) > 0
ORDER BY career_points DESC, career_goals DESC;
"""

# SQL to create goalie career stats view
create_goalie_view_sql = """
CREATE OR REPLACE VIEW goalie_career_stats AS
SELECT
    p.player_id,
    p.first_name,
    p.last_name,
    p.position,
    p.jersey_number,
    COUNT(DISTINCT ggs.game_id) as games_played,
    SUM(ggs.shots_against) as career_shots_against,
    SUM(ggs.saves) as career_saves,
    SUM(ggs.goals_against) as career_goals_against,
    SUM(ggs.minutes_played) as career_minutes,
    CASE
        WHEN SUM(ggs.shots_against) > 0
        THEN ROUND((SUM(ggs.saves)::numeric / SUM(ggs.shots_against)::numeric), 4)
        ELSE 0
    END as career_save_percentage,
    CASE
        WHEN SUM(ggs.minutes_played) > 0
        THEN ROUND((SUM(ggs.goals_against)::numeric / (SUM(ggs.minutes_played)::numeric / 60)), 2)
        ELSE 0
    END as goals_against_average,
    COUNT(CASE WHEN ggs.goals_against = 0 AND ggs.shots_against >= 15 THEN 1 END) as shutouts
FROM players p
LEFT JOIN goalie_game_stats ggs ON p.player_id = ggs.player_id
WHERE p.position = 'G'
GROUP BY p.player_id, p.first_name, p.last_name, p.position, p.jersey_number
HAVING COUNT(DISTINCT ggs.game_id) > 0
ORDER BY career_save_percentage DESC;
"""

# SQL to create season stats view
create_season_view_sql = """
CREATE OR REPLACE VIEW player_season_stats AS
SELECT
    p.player_id,
    p.first_name,
    p.last_name,
    p.position,
    p.jersey_number,
    g.season_id,
    t.team_code,
    t.team_name,
    COUNT(DISTINCT pgs.game_id) as games_played,
    SUM(pgs.goals) as goals,
    SUM(pgs.assists) as assists,
    SUM(pgs.points) as points,
    SUM(pgs.shots) as shots,
    SUM(pgs.pim) as pim,
    ROUND(SUM(pgs.points)::numeric / NULLIF(COUNT(DISTINCT pgs.game_id), 0), 2) as points_per_game
FROM players p
JOIN player_game_stats pgs ON p.player_id = pgs.player_id
JOIN games g ON pgs.game_id = g.game_id
JOIN teams t ON pgs.team_id = t.team_id
GROUP BY p.player_id, p.first_name, p.last_name, p.position, p.jersey_number,
         g.season_id, t.team_code, t.team_name
ORDER BY g.season_id DESC, points DESC;
"""

def create_views():
    """Create all career statistics views"""
    print("=" * 60)
    print("CREATING CAREER STATISTICS VIEWS")
    print("=" * 60)

    with engine.connect() as conn:
        try:
            # Create player career stats view
            print("\n📊 Creating player_career_stats view...")
            conn.execute(text(create_view_sql))
            conn.commit()
            print("✅ Created player_career_stats view")

            # Create goalie career stats view
            print("\n📊 Creating goalie_career_stats view...")
            conn.execute(text(create_goalie_view_sql))
            conn.commit()
            print("✅ Created goalie_career_stats view")

            # Create season stats view
            print("\n📊 Creating player_season_stats view...")
            conn.execute(text(create_season_view_sql))
            conn.commit()
            print("✅ Created player_season_stats view")

            print("\n✅ All views created successfully!")
            print("\nYou can now query:")
            print("  - SELECT * FROM player_career_stats;")
            print("  - SELECT * FROM goalie_career_stats;")
            print("  - SELECT * FROM player_season_stats;")

        except Exception as e:
            print(f"\n❌ Error creating views: {e}")
            raise

if __name__ == "__main__":
    create_views()
