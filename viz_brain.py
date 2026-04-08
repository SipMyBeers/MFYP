import sqlite3
import json

def draw_graph():
    conn = sqlite3.connect('mfyp_core.db')
    cursor = conn.cursor()
    
    # Fetch memories and their tags
    cursor.execute("SELECT id, content_snippet FROM embeddings LIMIT 15")
    nodes = cursor.fetchall()
    
    print("\n\033[1;36m[ MFYP: DITTO KNOWLEDGE GRAPH ]\033[0m")
    print("=" * 65)
    
    for i, (node_id, content) in enumerate(nodes):
        # Platform Icons
        icon = "𝕏" if "[X]" in content else "📸" if "Instagram" in content else "🌐"
        color = "\033[1;34m" if "[X]" in content else "\033[1;35m"
        
        # Draw Node
        snippet = content.replace("[X]", "").replace("[Instagram]", "").strip()[:45]
        print(f"{color}{icon} ID_{node_id[:4]}\033[0m ➔ {snippet}...")
        
        # Visual "Link" logic: if it's the 3rd node, show a branch (simulated graph)
        if i % 3 == 0 and i > 0:
            print("\033[38;5;244m  │   └─── Linked to 'Project Ditto' Cluster\033[0m")
            
    print("=" * 65)
    cursor.execute("SELECT COUNT(*) FROM embeddings")
    print(f"Neural Density: {cursor.fetchone()[0]} Active Nodes")
    conn.close()

if __name__ == "__main__":
    draw_graph()
