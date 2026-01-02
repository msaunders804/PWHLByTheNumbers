#!/usr/bin/env python3
"""
Migration Script: Add venue column to games table
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = 'postgresql://postgres:SecurePassword@localhost/pwhl_analytics'

def add_venue_column():
    """Add venue column to games table"""
    engine = create_engine(DATABASE_URL)

    print("Adding venue column to games table...")

    with engine.connect() as conn:
        # Check if column already exists
        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name='games' AND column_name='venue'
        """))

        if result.fetchone():
            print("  ⚠️  Venue column already exists!")
            return

        # Add the column
        conn.execute(text("ALTER TABLE games ADD COLUMN venue VARCHAR"))
        conn.commit()

        print("  ✅ Venue column added successfully!")

if __name__ == "__main__":
    add_venue_column()
