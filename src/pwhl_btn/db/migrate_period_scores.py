"""
migrate_period_scores.py — Add period score columns to the games table.

Safe to run multiple times — skips columns that already exist.

Usage:
    python -m pwhl_btn.db.migrate_period_scores
"""

from sqlalchemy import text
from pwhl_btn.db.db_config import get_engine

COLUMNS = [
    ("home_score_p1", "INT NULL"),
    ("home_score_p2", "INT NULL"),
    ("home_score_p3", "INT NULL"),
    ("away_score_p1", "INT NULL"),
    ("away_score_p2", "INT NULL"),
    ("away_score_p3", "INT NULL"),
]


def main():
    engine = get_engine()

    with engine.begin() as conn:
        # Get existing columns
        rows = conn.execute(text("SHOW COLUMNS FROM games")).fetchall()
        existing = {r[0] for r in rows}

        for col_name, col_def in COLUMNS:
            if col_name in existing:
                print(f"  {col_name}: already exists — skipped")
            else:
                conn.execute(text(f"ALTER TABLE games ADD COLUMN {col_name} {col_def}"))
                print(f"  {col_name}: added")

    print("\nMigration complete.")


if __name__ == "__main__":
    main()
