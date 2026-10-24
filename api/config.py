"""Load local settings once. Deployment can supply environment variables instead."""
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from redis import Redis

load_dotenv(Path(__file__).with_name(".env"))
SESSION_TTL = 24 * 60 * 60


class ConfigurationError(Exception):
    pass


@lru_cache
def get_redis():
    url = os.getenv("REDIS_URL", "").strip()
    if not url:
        raise ConfigurationError("Set REDIS_URL in api/.env.")
    if not url.startswith(("redis://", "rediss://")):
        raise ConfigurationError("REDIS_URL must be a redis:// or rediss:// connection URL.")
    return Redis.from_url(url, decode_responses=True, socket_connect_timeout=5, socket_timeout=5)
