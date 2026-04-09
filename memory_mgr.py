# SUPERSEDED — pre-Gormers DittoMeThis era file. Kept for reference.
```python
import sqlite3
from datetime import datetime

conn = sqlite3.connect('apfel_memory.db')
cursor = conn.cursor()

# Create table if it doesn't exist
cursor.execute('''
    CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL
    )
''')
conn.commit()

def save_exchange(role, content):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('INSERT INTO history (timestamp, role, content) VALUES (?, ?, ?)', (timestamp, role, content))
    conn.commit()

def get_recent_context(limit=5):
    cursor.execute('SELECT * FROM history ORDER BY timestamp DESC LIMIT ?', (limit,))
    rows = cursor.fetchall()
    recent_history = '\n'.join([f'{row[0]} - {row[1]} - {row[2]}\n' for row in rows])
    return recent_history

# Example usage:
save_exchange('admin', 'Updated system settings')
save_exchange('user', 'Requesting help')

recent_context = get_recent_context()
print(recent_context)
```
