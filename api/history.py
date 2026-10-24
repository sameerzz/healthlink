"""Read and write conversation history in Redis, separate from clinic data."""
import json

import config


def load_history(user_id):
    saved = config.get_redis().get(f"healthlink:history:{user_id}")
    return json.loads(saved) if saved else {"user_id": user_id, "messages": [], "phase": "intake"}


def save_history(user_id, state):
    config.get_redis().setex(f"healthlink:history:{user_id}", config.SESSION_TTL, json.dumps(state))


def turn_lock(user_id):
    # Prevent two simultaneous messages from overwriting the same conversation.
    return config.get_redis().lock(f"healthlink:turn:{user_id}", timeout=120, blocking_timeout=1)
