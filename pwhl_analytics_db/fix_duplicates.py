#!/usr/bin/env python3
"""
Fix Duplicate Stats in Database
Removes duplicate player and goalie game stats, keeping only the first record for each game
"""

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from db_models import PlayerGameStats, GoalieGameStats

DATABASE_URL = 'postgresql://postgres:SecurePassword@localhost/pwhl_analytics'
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

def fix_player_duplicates():
    """Remove duplicate player game stats"""
    session = Session()

    try:
        print("=" * 80)
        print("FIXING DUPLICATE PLAYER GAME STATS")
        print("=" * 80)

        # Find all game_id + player_id combinations with duplicates
        duplicates = session.query(
            PlayerGameStats.game_id,
            PlayerGameStats.player_id,
            func.count(PlayerGameStats.id).label('count'),
            func.min(PlayerGameStats.id).label('keep_id')
        ).group_by(
            PlayerGameStats.game_id,
            PlayerGameStats.player_id
        ).having(
            func.count(PlayerGameStats.id) > 1
        ).all()

        print(f"\nFound {len(duplicates)} player/game combinations with duplicates")

        if not duplicates:
            print("✓ No duplicates to fix!")
            return

        total_deleted = 0

        for dup in duplicates:
            # Delete all records EXCEPT the one with minimum ID
            deleted = session.query(PlayerGameStats).filter(
                PlayerGameStats.game_id == dup.game_id,
                PlayerGameStats.player_id == dup.player_id,
                PlayerGameStats.id != dup.keep_id
            ).delete()

            total_deleted += deleted

        session.commit()
        print(f"\n✅ Deleted {total_deleted} duplicate player stat records")

    except Exception as e:
        session.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        session.close()


def fix_goalie_duplicates():
    """Remove duplicate goalie game stats"""
    session = Session()

    try:
        print("\n" + "=" * 80)
        print("FIXING DUPLICATE GOALIE GAME STATS")
        print("=" * 80)

        # Find all game_id + player_id combinations with duplicates
        duplicates = session.query(
            GoalieGameStats.game_id,
            GoalieGameStats.player_id,
            func.count(GoalieGameStats.id).label('count'),
            func.min(GoalieGameStats.id).label('keep_id')
        ).group_by(
            GoalieGameStats.game_id,
            GoalieGameStats.player_id
        ).having(
            func.count(GoalieGameStats.id) > 1
        ).all()

        print(f"\nFound {len(duplicates)} goalie/game combinations with duplicates")

        if not duplicates:
            print("✓ No duplicates to fix!")
            return

        total_deleted = 0

        for dup in duplicates:
            # Delete all records EXCEPT the one with minimum ID
            deleted = session.query(GoalieGameStats).filter(
                GoalieGameStats.game_id == dup.game_id,
                GoalieGameStats.player_id == dup.player_id,
                GoalieGameStats.id != dup.keep_id
            ).delete()

            total_deleted += deleted

        session.commit()
        print(f"\n✅ Deleted {total_deleted} duplicate goalie stat records")

    except Exception as e:
        session.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        session.close()


def verify_fix():
    """Verify that duplicates are gone"""
    session = Session()

    try:
        print("\n" + "=" * 80)
        print("VERIFYING FIX")
        print("=" * 80)

        # Check for remaining player duplicates
        player_dups = session.query(
            PlayerGameStats.game_id,
            PlayerGameStats.player_id,
            func.count(PlayerGameStats.id).label('count')
        ).group_by(
            PlayerGameStats.game_id,
            PlayerGameStats.player_id
        ).having(
            func.count(PlayerGameStats.id) > 1
        ).count()

        # Check for remaining goalie duplicates
        goalie_dups = session.query(
            GoalieGameStats.game_id,
            GoalieGameStats.player_id,
            func.count(GoalieGameStats.id).label('count')
        ).group_by(
            GoalieGameStats.game_id,
            GoalieGameStats.player_id
        ).having(
            func.count(GoalieGameStats.id) > 1
        ).count()

        if player_dups == 0 and goalie_dups == 0:
            print("\n✅ SUCCESS! No duplicates remaining")
        else:
            print(f"\n⚠️  Still have duplicates:")
            print(f"   Player duplicates: {player_dups}")
            print(f"   Goalie duplicates: {goalie_dups}")

    finally:
        session.close()


if __name__ == "__main__":
    print("\n🔧 DATABASE DUPLICATE FIX UTILITY")
    print("This will remove duplicate player and goalie game stats\n")

    response = input("Continue? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled")
        exit(0)

    fix_player_duplicates()
    fix_goalie_duplicates()
    verify_fix()

    print("\n" + "=" * 80)
    print("✅ COMPLETE!")
    print("=" * 80)
    print("\nYou can now run career_stats.py to see correct totals")
