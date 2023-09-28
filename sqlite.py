import sqlite3
# Connect to SQLite database
conn = sqlite3.connect('news.db')
cursor = conn.cursor()

# Create table if not exists
cursor.execute('''
CREATE TABLE IF NOT EXISTS news (
    id TEXT PRIMARY KEY,
    author TEXT,
    title TEXT,
    url TEXT,
    publish_time TEXT,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP
)
''')

# Commit the transaction
conn.commit()
