import logging
import time
from typing import List, Tuple
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request
from jose import jwt
from jose.exceptions import JWTError
from pydantic import BaseModel
from sqlalchemy.exc import NoResultFound
from starlette.authentication import AuthCredentials, AuthenticationBackend, AuthenticationError, BaseUser
from starlette.requests import HTTPConnection
from starlette.responses import JSONResponse

from one_request.auth.enums import ApiVersion, PALANTIR_ROLE
from one_request.db.models import User, PalantirUser
from one_request.exceptions import ResourceNotFound

logger = logging.getLogger(__name__)


def get_token(authorization: str = Header()) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="No Authorization header provided")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    return authorization[7:]


Authorization = Depends(get_token)


class AuthUser(BaseUser):
    def __init__(self, user: User, api_version: ApiVersion):
        self.user = user
        self.api_version = api_version

    def __getattr__(self, item):
        if value := getattr(self.user, item, None):
            return value
        return super().__getattr__(item)

    @property
    def is_authenticated(self) -> bool:
        return self.user.id is not None

    @property
    def display_name(self) -> str:
        return self.user.name

    @property
    def identity(self) -> str:
        return self.user.role.value


class AuthCredentialsWithGroupKey(AuthCredentials):
    group_key: str | None

    def __init__(self, scopes: List[str], group_key: str | None):
        super().__init__(scopes)
        self.group_key = str(group_key) if group_key else None


class AuthBackend(AuthenticationBackend, BaseModel):
    jwt_secret: str | bytes
    jwt_algorithms: List[str]

    @staticmethod
    def on_error(_: Request, exc: Exception) -> JSONResponse:
        status_code, error_code, message = 401, None, str(exc)

        return JSONResponse(
            status_code=status_code,
            content={"error_code": error_code, "message": message},
        )

    async def authenticate(self, conn: HTTPConnection) -> Tuple[AuthCredentials, BaseUser] | None:
        authorization: str | None = conn.headers.get("Authorization")
        if not authorization:
            return None, None  # type: ignore

        try:
            scheme, credentials = authorization.split(" ")
            if scheme.lower() != "bearer":
                # if it's not bearer, we don't want it!
                return None, None  # type: ignore
        except ValueError as e:
            raise AuthenticationError("failed to parse Authorization Header") from e

        if not credentials:
            raise AuthenticationError("JWT not provided")

        try:
            payload = jwt.decode(
                credentials,
                self.jwt_secret,
                algorithms=self.jwt_algorithms,
            )
            user_id = payload.get("user_id")
        except JWTError as e:
            logger.warning(f"JWT Error: {e}")
            raise AuthenticationError("failed to parse JWT") from e
        except TypeError as e:
            logger.warning(f"Failed to parse user ID: {e}")
            raise AuthenticationError("Failed to parse User ID") from e

        if not user_id:
            logger.warning(f"user ID not provided in token: {payload=}")
            raise AuthenticationError("User ID not provided")

        if payload["expires"] < time.time():
            logger.debug(f"JWT Expired: {payload['expires']} < {time.time()}")
            raise AuthenticationError("JWT Expired")

        if payload["role"] == PALANTIR_ROLE:
            logger.debug(f"Palantir user: {user_id=}")
            # return AuthCredentials([PALANTIR_ROLE]), AuthUser(User(id=user_id), ApiVersion.PALANTIR_ROLE)
            return AuthCredentials([PALANTIR_ROLE]), PalantirUser(expiration=payload["expires"], user_id=user_id)

        try:
            user = User.one(User.id == UUID(user_id))
        except (NoResultFound, ResourceNotFound) as e:
            logger.debug(f"user not found: {user_id=}")
            raise AuthenticationError("Invalid User ID") from e

        logger.debug(f"user found: {user_id=} role={user.role}")
        return AuthCredentials([user.role.value]), AuthUser(user, ApiVersion(payload.get("api_version")))
