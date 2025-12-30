from sqlalchemy import create_engine
import sys
import os
from db_models import Base

# Replace 'your_password' with your actual postgres password
DATABASE_URL = 'postgresql://postgres:SecurePassword@localhost/pwhl_analytics'

engine = create_engine(DATABASE_URL)

# Create all tables
Base.metadata.create_all(engine)
print("Tables created successfully!")