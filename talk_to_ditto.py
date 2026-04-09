# SUPERSEDED — pre-Gormers DittoMeThis era file. Kept for reference.
import sqlite3
import json
import subprocess
from sentence_transformers import SentenceTransformer

def get_context(query):
    model = SentenceTransformer('all-MiniLM-L6-v2')
    q_vec = model.encode(query).tolist()
    conn = sqlite3.connect('mfyp_core.db')
    cursor = conn.cursor()
    cursor.execute("SELECT content_snippet FROM embeddings LIMIT 5")
    # In a real RAG we'd do vector math here, but for now we pull recent context
    rows = cursor.fetchall()
    conn.close()
    return "\n".join([r[0] for r in rows])

def ask_gemma(query, context):
    prompt = f"System: You are DITTO, an AI agent. Use this context to answer:\n{context}\n\nUser: {query}"
    process = subprocess.Popen(['ollama', 'run', 'gemma4:26b', prompt], 
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, _ = process.communicate()
    return stdout

if __name__ == "__main__":
    import sys
    query = sys.argv[1] if len(sys.argv) > 1 else "How does Pi AI connect to my work?"
    context = get_context(query)
    print(f"\033[1;32m░ DITTO (Gemma 4) IS THINKING...\033[0m")
    response = ask_gemma(query, context)
    print(response)
