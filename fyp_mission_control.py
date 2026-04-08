import sqlite3
import subprocess
import re
import os

def play_video(url):
    os.system('clear')
    print(f"\033[1;33m░ DITTO VISION: GRID-LOCKED... (Press 'q' to return)\033[0m")
    
    # Using 'tct' for the most stable terminal-locked render on M4
    subprocess.run([
        "mpv", 
        "--vo=tct",
        "--quiet", 
        "--loop-file",
        "--no-osc",
        url
    ])

def render_fyp():
    db_path = os.path.expanduser('~/Projects/MFYP/mfyp_core.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Fetch content and platform to build the menu
    cursor.execute("SELECT content, platform FROM ingestion_log ORDER BY id DESC LIMIT 20")
    rows = cursor.fetchall()
    
    os.system('clear')
    print(f"\n\033[1;36m[ MFYP | MULTIMODAL MISSION CONTROL ]\033[0m")
    print("━" * 75)
    
    for i, (content, platform) in enumerate(rows):
        icons = {"Instagram": "📸", "Reddit": "👾", "X": "𝕏", "YouTube": "📺"}
        p_clean = platform.strip("[]")
        icon = icons.get(p_clean, "🌐")
        
        vid_match = re.search(r"\[VIDEO:(.*?)\]", content)
        clean_text = re.sub(r"\[(VIDEO|IMG|STATS|TRANSCRIPT|COMMENTS):.*?\]", "", content).strip()
        
        indicator = "▶ " if vid_match else "  "
        print(f"{i+1:2d}. {indicator}{icon} | {clean_text[:65]}...")

    print("━" * 75)
    print("\033[1;32mCOMMANDS: <num> to Play | /exit\033[0m")
    
    try:
        user_choice = input("\nMFYP >> ").strip()
        if user_choice == "/exit": os._exit(0)
        
        # Selection Logic Fix: Explicitly target the chosen row
        idx = int(user_choice) - 1
        if 0 <= idx < len(rows):
            target_content = rows[idx][0]
            vid_url_match = re.search(r"\[VIDEO:(.*?)\]", target_content)
            
            if vid_url_match:
                play_video(vid_url_match.group(1))
            else:
                print("\033[1;31m(!) No video link in this entry.\033[0m")
                input("Press Enter...")
    except (ValueError, IndexError):
        print("\033[1;31m(!) Invalid selection.\033[0m")
    except KeyboardInterrupt:
        os._exit(0)
    finally:
        conn.close()

if __name__ == "__main__":
    while True:
        render_fyp()
