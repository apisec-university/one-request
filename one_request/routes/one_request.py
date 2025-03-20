from typing import Annotated

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field, computed_field

from one_request.ctf.validators import (
    validate_admin_key,
    validate_group,
    validate_activity,
    validate_location,
    validate_user,
    validate_invite_code,
)
from one_request.exceptions import ValidationError

router = APIRouter(tags=["One Request"])


class OneRequestIn(BaseModel):
    invite_code: str
    user_id: str


class OneRequestItemOut(BaseModel):
    valid: bool = False
    reason: str | None = None


class OneRequestOut(BaseModel):
    admin_key: OneRequestItemOut = Field(default_factory=OneRequestItemOut)
    group_id: OneRequestItemOut = Field(default_factory=OneRequestItemOut)
    activity_id: OneRequestItemOut = Field(default_factory=OneRequestItemOut)
    location_id: OneRequestItemOut = Field(default_factory=OneRequestItemOut)
    user_id: OneRequestItemOut = Field(default_factory=OneRequestItemOut)
    invite_code: OneRequestItemOut = Field(default_factory=OneRequestItemOut)

    @computed_field
    @property
    def flag(self) -> str | None:
        checks = [
            self.admin_key.valid,
            self.group_id.valid,
            self.activity_id.valid,
            self.location_id.valid,
            self.user_id.valid,
            self.invite_code.valid,
        ]
        return "onerequest{osgiliath_passages_protect_us}" if all(checks) else None


@router.post(
    "/one/request/groups/{group_id}/activities/{activity_id}/schedule/{location_id}",
    # no auth dependency so we can return better error messages later
    # dependencies=[OAuth(RequireApiVersion(ApiVersion.PALANTIR_ROLE))],
)
async def one_request(
    group_id: str = None,
    activity_id: str = None,
    location_id: str = None,
    data: OneRequestIn = None,
    authorization: Annotated[str | None, Header()] = None,
) -> OneRequestOut:
    response = OneRequestOut()

    try:
        await validate_admin_key(authorization)
        response.admin_key.valid = True
    except ValidationError as e:
        response.admin_key.reason = str(e)

    try:
        validate_group(group_id)
        response.group_id.valid = True
    except ValidationError as e:
        response.group_id.reason = str(e)

    try:
        validate_activity(activity_id)
        response.activity_id.valid = True
    except ValidationError as e:
        response.activity_id.reason = str(e)

    try:
        validate_location(location_id)
        response.location_id.valid = True
    except ValidationError as e:
        response.location_id.reason = str(e)

    try:
        validate_user(data.user_id if data else None)
        response.user_id.valid = True
    except ValidationError as e:
        response.user_id.reason = str(e)

    try:
        validate_invite_code(data.invite_code if data else None)
        response.invite_code.valid = True
    except ValidationError as e:
        response.invite_code.reason = str(e)

    return response
