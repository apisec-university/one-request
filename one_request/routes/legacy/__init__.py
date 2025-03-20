from typing import Dict, Any
from uuid import UUID

from fastapi import APIRouter, status, HTTPException

from one_request.auth.dependency import RequireSelf
from one_request.auth.enums import UserRole
from one_request.db.models import User

from . import support
from one_request.auth.dependency import RequireApiVersion, OAuth
from one_request.auth.enums import ApiVersion

router = APIRouter(dependencies=[OAuth(RequireApiVersion(ApiVersion.LEGACY))])
router.include_router(support.router, prefix="/support")


@router.patch(
    "/users/{user_id}",
    tags=["Users"],
    response_model=User,
    status_code=status.HTTP_200_OK,
    summary="Update a user",
    dependencies=[OAuth([RequireSelf("user_id"), UserRole.ADMIN])],
)
async def update_user(user_id: UUID, data: Dict[str, Any]) -> User:
    """Mass assignment vulnerable endpoint"""
    # todo WARNING: including relations on this first query somehow includes all groups within the user object,
    #      regardless of the primary_group_name. Very odd behavior,
    #      and attempts to delete UserGroupLinks when save(merge=True)
    user = User.one(User.id == user_id)
    # disallow updates to some fields
    forbidden = {"id", "role"}
    # disallow updates to relationships
    forbidden.update(user.__sqlmodel_relationships__.keys())

    for key, value in data.items():
        if key in forbidden:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"message": "requested change of a forbidden key", "key": key, "value": value},
            )

        if not getattr(user, key, None):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": "requested key not found", "key": key, "value": value},
            )

        setattr(user, key, value)

    user.save()
    return User.one(User.id == user_id, relations=True)
