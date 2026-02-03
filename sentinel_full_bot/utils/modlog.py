from datetime import datetime
from collections import defaultdict
import json
import os

# In-memory cache
USER_HISTORY = defaultdict(list)
MODLOG_FILE = "data/modlog.json"


def _load_modlog() -> dict:
    """Load modlog from file"""
    if not os.path.exists(MODLOG_FILE):
        return {}
    
    try:
        with open(MODLOG_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}


def _save_modlog(data: dict):
    """Save modlog to file"""
    os.makedirs("data", exist_ok=True)
    with open(MODLOG_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def _load_cache():
    """Load modlog from file into cache on startup"""
    data = _load_modlog()
    for user_id_str, actions in data.items():
        user_id = int(user_id_str)
        for action in actions:
            # Convert timestamp string back to datetime
            action["timestamp"] = datetime.fromisoformat(action["timestamp"])
            USER_HISTORY[user_id].append(action)


def log_action(
    *,
    action: str,
    target_id: int,
    moderator: str,
    reason: str | None = None,
    extra: dict | None = None
):
    """Log an action and persist to file"""
    entry = {
        "action": action,
        "moderator": moderator,
        "reason": reason or "No reason provided",
        "extra": extra or {},
        "timestamp": datetime.utcnow()
    }
    
    USER_HISTORY[target_id].append(entry)
    
    # Persist to file
    data = _load_modlog()
    target_id_str = str(target_id)
    
    if target_id_str not in data:
        data[target_id_str] = []
    
    # Convert to serializable format
    data[target_id_str].append({
        "action": action,
        "moderator": moderator,
        "reason": reason or "No reason provided",
        "extra": extra or {},
        "timestamp": datetime.utcnow().isoformat()
    })
    
    _save_modlog(data)


def get_history(user_id: int):
    """Get history for a user"""
    return USER_HISTORY.get(user_id, [])


# Load modlog on import
_load_cache()

