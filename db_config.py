"""
db_config.py — Central database connection config.
Priority:
  1. .env file in project root
  2. PWHL_DATABASE_URL environment variable
  3. Interactive prompt (fallback for first-time setup)
"""

import os
import getpass
from pathlib import Path


def get_db_url() -> str:
    # 1. Try loading .env from project root (parent of this file's directory)
    _load_dotenv()

    # 2. Check env var (set directly or loaded from .env)
    url = os.environ.get("PWHL_DATABASE_URL")
    if url:
        return url

    # 3. Interactive fallback
    print("\nMySQL Connection")
    print("-" * 30)
    host     = input("Host     [localhost]: ").strip() or "localhost"
    port     = input("Port     [3306]:     ").strip() or "3306"
    user     = input("User     [root]:     ").strip() or "root"
    password = getpass.getpass("Password:            ")
    db       = input("Database [pwhl_analytics]: ").strip() or "pwhl_analytics"

    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}"


def _load_dotenv():
    """Load .env without requiring python-dotenv to be installed."""
    # Look for .env in the same dir as this file, or one level up
    candidates = [
        Path(__file__).parent / ".env",
        Path(__file__).parent.parent / ".env",
    ]
    for env_path in candidates:
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, val = line.partition("=")
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = val
            break
