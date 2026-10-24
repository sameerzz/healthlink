"""Issue an anonymous session token and validate it on later requests."""
from secrets import token_urlsafe

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.exceptions import RedisError

import config
from config import ConfigurationError
from database import create_user, user_exists

bearer = HTTPBearer(auto_error=False)


def create_session():
    user_id = create_user()
    token = token_urlsafe(32)
    config.get_redis().setex(f"healthlink:session:{token}", config.SESSION_TTL, user_id)
    return {"user_id": user_id, "token": token, "expires_in": config.SESSION_TTL}


def require_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    if credentials is None:
        raise HTTPException(status_code=401, detail="Start a session first.")
    try:
        user_id = config.get_redis().get(f"healthlink:session:{credentials.credentials}")
    except (RedisError, ConfigurationError):
        raise HTTPException(status_code=503, detail="Session storage is unavailable. Check REDIS_URL.") from None
    if not user_id or not user_exists(user_id):
        raise HTTPException(status_code=401, detail="Session expired or invalid. Start a new chat.")
    return user_id
