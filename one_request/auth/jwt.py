from time import time
from typing import Any, Dict

from jose import jwt

from one_request.config import config
from one_request.db.models import User


def sign_jwt(user: User, extra: Dict[str, Any] | None = None) -> str:
    payload = {
        **(extra or {}),
        "user_id": str(user.id),
        "name": user.name,
        "email": user.email,
        "role": user.role.value if user.role else None,
        "expires": time() + config.auth.jwt.expiration,
    }
    token = jwt.encode(payload, config.auth.jwt.secret_key, algorithm=config.auth.jwt.algorithm)

    return token
