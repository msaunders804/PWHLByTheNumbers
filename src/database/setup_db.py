from sqlalchemy import create_engine
import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from src.database.db_models import Base

# Replace 'your_password' with your actual postgres password
DATABASE_URL = 'postgresql://postgres:SecurePassword@localhost/pwhl_analytics'

engine = create_engine(DATABASE_URL)

# Create all tables
Base.metadata.create_all(engine)
print("Tables created successfully!")