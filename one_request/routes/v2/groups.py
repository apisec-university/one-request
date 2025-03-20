from typing import Sequence
from uuid import UUID

from fastapi import APIRouter, status, HTTPException
from starlette.requests import Request

from one_request.auth.dependency import OAuth
from one_request.auth.enums import UserRole
from one_request.db.models import Group, User, GroupCreate, GroupEdit, Empty, UserGroupLink

router = APIRouter(tags=["Groups"])


@router.get(
    "/",
    response_model=list[Group],
    status_code=status.HTTP_200_OK,
    summary="Fetch all Groups",
    dependencies=[OAuth(UserRole.ADMIN)],
)
async def get() -> Sequence[Group]:
    return Group.all(relations=True)


@router.post(
    "/",
    response_model=Group,
    status_code=status.HTTP_200_OK,
    summary="Create a Group",
    dependencies=[OAuth()],
)
async def get(data: GroupCreate, request: Request) -> Group:
    return Group(
        **data.model_dump(),
        owner_id=request.user.id,
        users=[request.user],
    ).save()


@router.put(
    "/{group_id}",
    response_model=Group,
    status_code=status.HTTP_200_OK,
    summary="Update a Group by ID",
    dependencies=[OAuth()],
)
async def delete(group_id: UUID, data: GroupEdit, request: Request) -> Group:
    group = Group.one(Group.id == group_id)
    if request.user.role != UserRole.ADMIN and request.user.id != group.owner_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "You do not have permission to modify this group"},
        )

    for key in data.model_fields:
        value = getattr(data, key)
        if value is Empty:
            continue

        setattr(group, key, value)

    return group.save()


@router.delete(
    "/{group_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a Group by ID",
    dependencies=[OAuth()],
)
async def delete(group_id: UUID, request: Request):
    group = Group.one(Group.id == group_id)
    if request.user.role != UserRole.ADMIN and request.user.id != group.owner_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "You do not have permission to modify this group"},
        )

    group.delete()


@router.get(
    "/{group_id}/members",
    response_model=list[User],
    status_code=status.HTTP_200_OK,
    summary="Get members of a group",
    dependencies=[OAuth()],
)
async def delete(group_id: UUID, request: Request) -> list[User]:
    group = Group.one(Group.id == group_id, relations=["users"])
    user_ids = map(lambda g: g.id, group.users)
    if request.user.role != UserRole.ADMIN and request.user.id not in user_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "You do not have permission to view this group's membership"},
        )

    return group.users


@router.put(
    "/{group_id}/members/{user_id}",
    response_model=Group,
    status_code=status.HTTP_200_OK,
    summary="Add a member to a group",
    dependencies=[OAuth()],
)
async def add(group_id: UUID, user_id: UUID, request: Request) -> Group:
    group = Group.one(Group.id == group_id, relations=["users"])
    user = User.one(User.id == user_id)
    if request.user.role != UserRole.ADMIN and request.user.id != group.owner_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "You do not have permission to modify this group"},
        )

    if UserGroupLink.first(UserGroupLink.group_id == group_id, UserGroupLink.user_id == user_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already a member of this group")

    UserGroupLink(user_id=user_id, group_id=group_id).save()
    return group.refresh()


@router.delete(
    "/{group_id}/members/{user_id}",
    response_model=Group,
    status_code=status.HTTP_200_OK,
    summary="Add a member to a group",
    dependencies=[OAuth()],
)
async def delete(group_id: UUID, user_id: UUID, request: Request) -> Group:
    group = Group.one(Group.id == group_id, relations=["users"])
    if request.user.role != UserRole.ADMIN and request.user.id != group.owner_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "You do not have permission to modify this group"},
        )

    link = UserGroupLink.first(UserGroupLink.group_id == group_id, UserGroupLink.user_id == user_id)
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not a member of this group")

    link.delete()
    return group.refresh()
