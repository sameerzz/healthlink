"""Load local settings once. Deployment can supply environment variables instead."""
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from redis import Redis

load_dotenv(Path(__file__).with_name(".env"))
SESSION_TTL = 24 * 60 * 60

# Change these two settings here to switch the model used by every agent.
# Providers: "openrouter", "openai", "gemini" ("google" is also accepted).
MODEL_PROVIDER = "openrouter"
MODEL_NAME = os.getenv("OPENROUTER_MODEL", "").strip()  # Or set a model ID directly.

MODEL_PROVIDERS = {
    "openrouter": ("https://openrouter.ai/api/v1", ("OPENROUTER_API_KEY",)),
    "openai": ("https://api.openai.com/v1", ("OPENAI_API_KEY",)),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/",
               ("GEMINI_API_KEY", "GOOGLE_API_KEY")),
}


class ConfigurationError(Exception):
    pass


def get_model_settings():
    provider = MODEL_PROVIDER.strip().lower()
    if provider == "google":
        provider = "gemini"
    if provider not in MODEL_PROVIDERS:
        raise ConfigurationError("MODEL_PROVIDER in api/config.py must be openrouter, openai, or gemini.")
    if not MODEL_NAME.strip():
        raise ConfigurationError("Set MODEL_NAME in api/config.py to a model ID for your provider.")
    base_url, key_names = MODEL_PROVIDERS[provider]
    key = next((os.environ[name].strip() for name in key_names
                if os.getenv(name, "").strip()), "")
    if not key:
        raise ConfigurationError(f"Set {' or '.join(key_names)} in api/.env for {provider}.")
    return {"api_key": key, "base_url": base_url, "model": MODEL_NAME.strip()}


@lru_cache
def get_redis():
    url = os.getenv("REDIS_URL", "").strip()
    if not url:
        raise ConfigurationError("Set REDIS_URL in api/.env.")
    if not url.startswith(("redis://", "rediss://")):
        raise ConfigurationError("REDIS_URL must be a redis:// or rediss:// connection URL.")
    return Redis.from_url(url, decode_responses=True, socket_connect_timeout=5, socket_timeout=5)
