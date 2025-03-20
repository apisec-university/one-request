from typing import Sequence, Dict, Any
from uuid import UUID

from fastapi import APIRouter, status, HTTPException

from one_request.auth.dependency import OAuth, RequireSelf
from one_request.auth.enums import UserRole
from one_request.db.models import Group, User

router = APIRouter(tags=["Users"])


@router.get(
    "/",
    response_model=list[User],
    status_code=status.HTTP_200_OK,
    summary="Fetch all users",
    dependencies=[OAuth(UserRole.ADMIN)],
)
async def users() -> Sequence[User]:
    return User.all(relations=True)


@router.delete(
    "/{user_id}",
    response_model=User,
    status_code=status.HTTP_200_OK,
    summary="Delete a user by ID",
    dependencies=[OAuth([RequireSelf("user_id"), UserRole.ADMIN])],
)
async def delete(user_id: UUID) -> User:
    user = User.one(User.id == user_id)
    user.role = UserRole.DELETED
    return user.save()
