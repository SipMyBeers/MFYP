import sqlite3
from sentence_transformers import SentenceTransformer
import json
import numpy as np

def cosine_similarity(v1, v2):
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

def query_brain(user_query, db_path='mfyp_core.db'):
    model = SentenceTransformer('all-MiniLM-L6-v2')
    query_vector = model.encode(user_query).tolist()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT embedding_vector, content_snippet FROM embeddings")
    rows = cursor.fetchall()
    
    results = []
    for row in rows:
        db_vector = json.loads(row[0])
        score = cosine_similarity(query_vector, db_vector)
        results.append((score, row[1]))
    
    # Sort by highest similarity
    results.sort(key=lambda x: x[0], reverse=True)
    
    print(f"\n░ QUERY: {user_query}")
    print("░ TOP RELEVANT DATA FOUND:")
    for score, snippet in results[:2]:
        print(f"  - [Score: {score:.4f}] {snippet[:150]}...")
    
    conn.close()

if __name__ == "__main__":
    import sys
    query = sys.argv[1] if len(sys.argv) > 1 else "What is this domain for?"
    query_brain(query)
