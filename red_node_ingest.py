# SUPERSEDED — pre-Gormers DittoMeThis era file. Kept for reference.
import sqlite3
import requests
from bs4 import BeautifulSoup
import urllib3
import sys

# Suppress SSL warnings for local dev
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def ingest_url(target_url, entity_id, db_path='mfyp_core.db'):
    try:
        # Fetching content with SSL verification disabled for M4 local env
        response = requests.get(target_url, timeout=10, verify=False)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        for script in soup(["script", "style"]):
            script.decompose()
        clean_text = soup.get_text(separator=' ', strip=True)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Link content to the specified entity_id
        cursor.execute('''
            INSERT INTO ingestion_log (entity_id, url, content, processed_status)
            VALUES (?, ?, ?, ?)
        ''', (entity_id, target_url, clean_text, 'pending'))
        
        conn.commit()
        conn.close()
        print(f"░ SUCCESS: Data ingested for Entity [{entity_id}] from {target_url}")
        
    except Exception as e:
        print(f"░ SYSTEM_FAULT: {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) > 2:
        ingest_url(sys.argv[1], sys.argv[2])
    else:
        print("░ USAGE: python3 red_node_ingest.py <url> <entity_id>")
