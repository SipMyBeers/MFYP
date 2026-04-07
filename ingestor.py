```python
import sqlite3
from datetime import datetime

class UniversalPost:
    def __init__(self, id, platform, author, content, timestamp, raw_json):
        self.id = id
        self.platform = platform
        self.author = author
        self.content = content
        self.timestamp = timestamp
        self.raw_json = raw_json


def standardize_instagram(json_data):
    """
    Convert Instagram-CLI format to standard format.

    Args:
        json_data (dict): JSON data from Instagram CLI.

    Returns:
        dict: Standardized data structure.
    """
    post = {
        "id": json_data["id"],
        "platform": "Instagram",
        "author": json_data["author"],
        "content": json_data["content"],
        "timestamp": json_data["created_time"],
        "raw_json": json_data
    }
    return post


def standardize_twitter(json_data):
    """
    Convert Twitter format to standard format.

    Args:
        json_data (dict): JSON data from Twitter format.

    Returns:
        dict: Standardized data structure.
    """
    post = {
        "id": json_data["id"],
        "platform": "Twitter",
        "author": json_data["user"]["name"],
        "content": json_data["full_text"],
        "timestamp": json_data["created_at"],
        "raw_json": json_data
    }
    return post


def save_to_db(posts):
    """
    Save posts to a local SQLite database.

    Args:
        posts (list): List of posts to be saved.
    """
    conn = sqlite3.connect('mfyp.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS feed (
                        id INTEGER PRIMARY KEY,
                        platform TEXT,
                        author TEXT,
                        content TEXT,
                        timestamp TEXT,
                        raw_json TEXT)''')
    for post in posts:
        cursor.execute('''INSERT INTO feed (id, platform, author, content, timestamp, raw_json)
                           VALUES (?, ?, ?, ?, ?, ?)''',
                       (post['id'], post['platform'], post['author'], post['content'], post['timestamp'], post['raw_json']))
    conn.commit()
    conn.close()


if __name__ == '__main__':
    # Example JSON data
    instagram_data = {
        "id": 1,
        "author": "user123",
        "content": "This is an Instagram post.",  # e.g. "text content"
        "created_time": "2023-10-10T10:00:00"
    }
    twitter_data = {
        "id": 2,
        "user": {"name": "user456"},
        "full_text": "Check out this tweet!",  # e.g. "tweet content"
        "created_at": "2023-10-10T10:05:00"
    }

    standardized_instagram = standardize_instagram(instagram_data)
    standardized_twitter = standardize_twitter(twitter_data)

    posts = [standardized_instagram, standardized_twitter]
    save_to_db(posts)
    print("Posts saved to database successfully.")
```
