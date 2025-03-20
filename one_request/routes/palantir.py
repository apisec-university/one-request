from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header
from starlette.requests import Request

from one_request.auth.dependency import OAuth, RequireApiVersion
from one_request.auth.enums import UserRole, ApiVersion
from one_request.ctf.validators import (
    generate_glimpse_token,
)
from one_request.db.models import Chat
from one_request.exceptions import ApiRoleException
from one_request.routes.one_request import OneRequestOut, OneRequestIn, one_request

router = APIRouter(
    include_in_schema=False,
    tags=["PALANTIR"],
)

DISCLAIMER = """
!!WARNING!! AUTHORIZED ACCESS ONLY !!WARNING!!

By the authority of the White Council and decree of the Steward of Gondor:

This is a protected realm of the Free Peoples of Middle-earth. You are accessing systems maintained by the Istari Order under the oversight of the White Council. Unauthorized access, misuse, or disclosure of administrative privileges shall be met with consequences dire as the depths of Moria.

Your actions within these halls are being recorded in the Scrolls of Watching, maintained by the Guardians of the Citadel. Any attempt to breach, circumvent, or misuse these powers will result in immediate banishment to the wastelands beyond the walls of trust, where the eyes of Mordor ever watch.

Those who wield administrative authority must do so with the wisdom of Elrond, the caution of Faramir, and the honor of Aragorn. Remember always that with great power comes the burden of guardianship over the realms of others.

May your path be true and your intentions pure, lest you face judgment before the Council of the Wise.

------------------
"All we have to decide is what to do with the time that is given us." - Gandalf the Grey
"""


@router.post("/glimpse", dependencies=[OAuth(RequireApiVersion(ApiVersion.LEGACY))])
async def admin_token(request: Request):
    # auth is required to get here, so we don't need to validate the existing token - just the user's role
    # we could require a different token set entirely though
    if request.user.role == UserRole.USER:
        raise ApiRoleException(request.user.role)

    return {
        # 5 min validity - use it quick!
        "access_token": generate_glimpse_token(str(request.user.id), expiration=300),
        "token_type": "bearer",
        "_disclaimer": DISCLAIMER,
    }


@router.post(
    "/groups/{group_id}/activities/{activity_id}/schedule/{location_id}",
    # no auth dependency so we can return better error messages later
    # dependencies=[OAuth(RequireApiVersion(ApiVersion.PALANTIR_ROLE))],
)
async def one_request_alias(
    group_id: str = None,
    activity_id: str = None,
    location_id: str = None,
    data: OneRequestIn = None,
    authorization: Annotated[str | None, Header()] = None,
) -> OneRequestOut:
    return await one_request(group_id, activity_id, location_id, data, authorization)


@router.get("/groups/{group_id}/chats", dependencies=[OAuth(RequireApiVersion(ApiVersion.PALANTIR_ROLE))])
def group_chats(group_id: UUID):
    return Chat.all(Chat.group_id == group_id, relations=["messages", "group"])
