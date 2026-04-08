import sqlite3

def ingest_reddit_knowledge(post_data):
    conn = sqlite3.connect('../mfyp_core.db')
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO ingestion_log (content, platform, description, comments) 
        VALUES (?, ?, ?, ?)
    """, (post_data['url'], 'Reddit', post_data['title'], post_data['top_comments']))
    conn.commit()
    conn.close()
