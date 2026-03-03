"""
setup_db.py — Drop and rebuild all PWHL analytics tables (MySQL).

Usage:
    python setup_db.py
    python setup_db.py --confirm
"""

import sys, argparse
from sqlalchemy import create_engine, text
from models import Base
from db_config import get_db_url


def rebuild(confirm: bool = False):
    if not confirm:
        print("WARNING: This will DROP all existing tables and data.")
        if input("Type 'yes' to continue: ").strip().lower() != "yes":
            print("Aborted.")
            sys.exit(0)

    engine = create_engine(get_db_url())

    with engine.connect() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        conn.commit()

    print("Dropping all tables...")
    Base.metadata.drop_all(engine)

    with engine.connect() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        conn.commit()

    print("Creating all tables...")
    Base.metadata.create_all(engine)

    with engine.connect() as conn:
        tables = [row[0] for row in conn.execute(text("SHOW TABLES"))]

    print(f"\nTables created: {', '.join(tables)}")
    print("\nDatabase ready for backfill.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    rebuild(confirm=args.confirm)
