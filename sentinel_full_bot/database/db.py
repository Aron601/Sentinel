import json
import os
from pathlib import Path
from datetime import datetime

# JSON file paths
USERS_FILE = Path(__file__).parent.parent / "data" / "users.json"
LOGS_FILE = Path(__file__).parent.parent / "data" / "mod_logs.json"

DB_ENABLED = True


async def connect():
    """
    Initialize JSON database files.
    Creates files if they don't exist.
    """
    global DB_ENABLED
    
    try:
        # Ensure data directory exists
        USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize users.json
        if not USERS_FILE.exists():
            USERS_FILE.write_text(json.dumps({}))
        
        # Initialize mod_logs.json
        if not LOGS_FILE.exists():
            LOGS_FILE.write_text(json.dumps([]))
        
        DB_ENABLED = True
        print("[DB] JSON Database initialized successfully.")
    except Exception as e:
        DB_ENABLED = False
        print("[DB] JSON Database initialization failed.")
        print("Reason:", e)


async def fetch_user(user_id: int):
    """
    Fetch a user from JSON or return defaults if not found.
    """
    if not DB_ENABLED:
        return {"id": user_id, "power": 0, "trust": 50}
    
    try:
        data = json.loads(USERS_FILE.read_text())
        user_key = str(user_id)
        
        if user_key in data:
            return data[user_key]
        
        # Create new user with defaults
        new_user = {"id": user_id, "power": 0, "trust": 50}
        data[user_key] = new_user
        USERS_FILE.write_text(json.dumps(data, indent=2))
        
        return new_user
    except Exception as e:
        print(f"[DB] Error fetching user {user_id}: {e}")
        return {"id": user_id, "power": 0, "trust": 50}


async def log_action(mod_id: int, action: str, target_id: int):
    """
    Log moderation actions to JSON file.
    """
    if not DB_ENABLED:
        print(f"[LOG] {action} | mod={mod_id} target={target_id}")
        return
    
    try:
        logs = json.loads(LOGS_FILE.read_text())
        logs.append({
            "mod_id": mod_id,
            "action": action,
            "target_id": target_id,
            "created_at": datetime.now().isoformat()
        })
        LOGS_FILE.write_text(json.dumps(logs, indent=2))
    except Exception as e:
        print(f"[DB] Error logging action: {e}")
