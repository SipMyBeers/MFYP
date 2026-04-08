import sqlite3
from sentence_transformers import SentenceTransformer
import json

def process_pending_ingestions(db_path='mfyp_core.db'):
    # Load a lightweight model that runs great on M4
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Grab everything labeled 'pending'
    cursor.execute("SELECT id, entity_id, content FROM ingestion_log WHERE processed_status = 'pending'")
    rows = cursor.fetchall()
    
    for row in rows:
        row_id, entity_id, content = row
        if not content: continue
        
        print(f"░ PROCESSING: ID {row_id} for Entity {entity_id}")
        
        # 2. Generate Vector
        vector = model.encode(content).tolist()
        vector_str = json.dumps(vector)
        
        # 3. Insert into Embeddings table
        cursor.execute('''
            INSERT INTO embeddings (entity_id, source_id, embedding_vector, content_snippet)
            VALUES (?, ?, ?, ?)
        ''', (entity_id, row_id, vector_str, content[:200]))
        
        # 4. Mark as processed
        cursor.execute("UPDATE ingestion_log SET processed_status = 'completed' WHERE id = ?", (row_id,))
        
    conn.commit()
    conn.close()
    print("░ SUCCESS: Brain update complete.")

if __name__ == "__main__":
    process_pending_ingestions()
