"""
Validate CTF Answers
"""
import asyncio
from time import time
from typing import TypeVar, Type
from uuid import UUID, uuid4

import jwt
from cincoconfig import generate_argparse_parser
from jose import JWTError
from sqlmodel import SQLModel

from one_request import setup, logging
from one_request.auth.enums import PALANTIR_ROLE
from one_request.config import config
from one_request.ctf.data import (
    TARGET_INVITE_CODE,
    TARGET_GROUP,
    TARGET_LOCATION,
    TARGET_USER,
    TARGET_ACTIVITY,
)
from one_request.db.models import Group, Activity, Location, User, RelationsT
from one_request.exceptions import ValidationError

logger = logging.getLogger(__name__)


def generate_glimpse_token(user_id: str, expiration=300):
    payload = {
        "user_id": user_id,
        "name": "ADMIN",
        "email": "root@palantir",
        "role": PALANTIR_ROLE,
        "expires": time() + expiration,
    }
    return jwt.encode(payload, config.auth.jwt.secret_key, algorithm=config.auth.jwt.algorithm)


T = TypeVar("T", bound=Type[SQLModel])


def lookup_model(value: str, model: T, relations: RelationsT = None) -> T:
    try:
        object_id = UUID(value)
    except ValueError:
        raise ValidationError("invalid uuid")

    try:
        return model.one(model.id == object_id, relations=relations)
    except Exception:
        raise ValidationError(f"{model.__name__} not found")


def validate_group(group_id: str | None):
    if not group_id:
        raise ValidationError("missing group_id from path parameters")

    group = lookup_model(group_id, Group)
    if not (group.name == TARGET_GROUP["name"] and group.description == TARGET_GROUP["description"]):
        raise ValidationError("incorrect group_id")


def validate_activity(activity_id: str | None):
    if not activity_id:
        raise ValidationError("missing activity_id from path parameters")

    activity = lookup_model(activity_id, Activity, relations=["creator"])
    # names can be duplicated, so don't rely on name
    if activity.name != TARGET_ACTIVITY["name"]:
        logger.info(f"activity name mismatch: {activity.name} != {TARGET_ACTIVITY['name']}")
        raise ValidationError("incorrect activity")

    # also verify invite code
    if not activity.check_invite_code(TARGET_INVITE_CODE):
        logger.info(f"activity invite code mismatch: {activity.invite_code} != {TARGET_INVITE_CODE}")
        raise ValidationError("incorrect activity, invite codes do not match")

    # and validate owner email
    if not activity.creator.email == TARGET_USER["email"]:
        logger.info(f"activity owner email mismatch: {activity.creator.email} != {TARGET_USER['email']}")
        raise ValidationError("incorrect activity, owner is incorrect")


def validate_location(location_id: str | None):
    if not location_id:
        raise ValidationError("missing location_id from path parameters")

    location = lookup_model(location_id, Location)
    if location.name != TARGET_LOCATION:
        # todo better feedback on finding the correct location
        raise ValidationError("incorrect location")


def validate_user(user_id: str | None):
    if not user_id:
        raise ValidationError("missing user_id from request body. Please send json containing `user_id`.")

    user = lookup_model(user_id, User)
    if not (user.email == TARGET_USER["email"] and user.name == TARGET_USER["name"]):
        raise ValidationError("incorrect user")


def validate_invite_code(invite_code: str | None):
    if not invite_code:
        raise ValidationError("missing invite_code from request body. Please send json containing `invite_code`.")

    # allow with or without the onerequest{} brackets
    if invite_code != TARGET_INVITE_CODE:
        raise ValidationError("incorrect invite_code")


async def validate_admin_key(admin_key: str | None):
    if not admin_key:
        raise ValidationError("missing admin key in Authorization header")

    try:
        parts = admin_key.split(" ")
        if len(parts) == 1:
            credentials = parts[0]
        else:
            scheme, credentials = parts
            scheme.strip()
            credentials.strip()
            if not credentials.startswith("ey") and scheme.startswith("ey"):
                # scheme might be the token, close enough
                credentials = scheme
    except ValueError as e:
        credentials = None

    if not credentials:
        raise ValidationError(f"failed to parse Authorization header: {admin_key}")

    try:
        payload = jwt.decode(credentials, config.auth.jwt.secret_key, algorithms=[config.auth.jwt.algorithm])
    except JWTError as e:
        raise ValidationError(f"failed to parse admin key as JWT: {e}")

    if payload.get("role") != PALANTIR_ROLE:
        raise ValidationError("admin key is not authorized for PALANTIR use")

    if payload["expires"] < time():
        raise ValidationError("admin key has expired")


async def debug():
    target_user = User.one(User.email == TARGET_USER["email"])
    target_group = Group.one(Group.name == TARGET_GROUP["name"])
    target_activity = Activity.one(Activity.name == TARGET_ACTIVITY["name"])
    target_location = Location.one(Location.name == TARGET_LOCATION)
    admin_key = generate_glimpse_token(str(uuid4()), expiration=60 * 60 * 24)
    # print target IDs
    print("target_user:", target_user.id)
    print("target_group:", target_group.id)
    print("target_activity:", target_activity.id)
    print("target_location:", target_location.id)
    print("invite_code:", TARGET_INVITE_CODE)
    print("admin_key:", admin_key)

    # validate lookups
    validate_group(str(target_group.id))
    validate_activity(str(target_activity.id))
    validate_location(str(target_location.id))
    validate_user(str(target_user.id))
    validate_invite_code(TARGET_INVITE_CODE)
    await validate_admin_key(admin_key)


if __name__ == "__main__":
    parser = generate_argparse_parser(config)
    args, _ = parser.parse_known_args()
    app = setup(args=args)
    asyncio.run(debug())
