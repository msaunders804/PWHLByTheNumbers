from db_config import get_db_url
url = get_db_url()
print('Connecting to:', url[:50], '...')
from sqlalchemy import create_engine, text
engine = create_engine(url)
with engine.connect() as conn:
    row = conn.execute(text('SELECT MAX(game_id) FROM games')).fetchone()
    print('Max game_id in DB:', row[0])