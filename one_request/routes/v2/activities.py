from datetime import date
from typing import Sequence, Optional
from uuid import UUID

from fastapi import APIRouter, status, HTTPException
from fastapi_pagination import Page
from starlette.requests import Request

from one_request.auth.dependency import OAuth, RequireGroupByName
from one_request.auth.enums import UserRole
from one_request.auth.hashers import BcryptPasswordHandler
from one_request.db.models import (
    Group,
    Location,
    Activity,
    Review,
    Booking,
    UserGroupLink,
    NewActivity,
    EditActivity,
    Empty,
)

router = APIRouter(tags=["Activities"])


@router.get(
    "/",
    response_model=Page[Activity],
    status_code=status.HTTP_200_OK,
    summary="Fetch all public activities",
)
async def get(
    name: Optional[str] = None,
    before: Optional[date] = None,
    after: Optional[date] = None,
    creator_id: Optional[UUID] = None,
    group_id: Optional[UUID] = None,
) -> Page[Activity]:
    where = []
    if name:
        where.append(Activity.name == name)
    if before:
        where.append(Activity.day <= before)
    if after:
        where.append(Activity.day <= after)
    if creator_id:
        where.append(Activity.creator_id == creator_id)

    if group_id:
        # this is a vulnerability to show private events within a group
        where.append(Activity.group_id == group_id)
    else:
        where.append(Activity.group_id == None)

    return Activity.paginate(
        *where,
        relations=[Location, Review],
    )


@router.post(
    "/",
    response_model=Activity,
    status_code=status.HTTP_200_OK,
    summary="Create a new Activity",
)
async def create(data: NewActivity, request: Request):
    if data.group_id:
        # check is user is a member of the group
        link = UserGroupLink.first(UserGroupLink.group_id == data.group_id, UserGroupLink.user_id == request.user.id)
        if not link:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to create an activity for this group",
            )

    activity = Activity(**data.model_dump())
    activity.creator_id = request.user.id
    if data.invite_code:
        activity.invite_code = BcryptPasswordHandler.hash(data.invite_code).hash
    return activity.save()


@router.put(
    "/{activity_id}",
    response_model=Activity,
    status_code=status.HTTP_200_OK,
    summary="Create a new Activity",
)
async def create(activity_id: UUID, data: EditActivity, request: Request):
    if data.group_id is not Empty:
        group = Group.one(Group.id == data.group_id)
        if group.owner_id != request.user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to create an activity for this group",
            )
    activity = Activity.one(Activity.id == activity_id)
    if activity.group_id:
        group = Group.one(Group.id == activity.group_id)
        if group.owner_id != request.user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to create an activity for this group",
            )

    for key in data.model_fields:
        value = getattr(data, key)
        if value is Empty:
            continue

        if key == "invite_code":
            value = BcryptPasswordHandler.hash(value).hash

        setattr(activity, key, value)

    return activity.save()


@router.get(
    "/groups/{group_name}",
    response_model=list[Activity],
    status_code=status.HTTP_200_OK,
    summary="Fetch all private activities for a given group",
    dependencies=[OAuth([RequireGroupByName("group_name"), UserRole.ADMIN])],
)
async def get(group_name: str) -> Sequence[Activity]:
    group = Group.one(Group.name == group_name)
    return Activity.private_activities(group.id)


@router.post(
    "/{activity_id}/schedule/{location_id}",
    status_code=status.HTTP_200_OK,
    summary="Create a new booking for an Activity at a Location",
)
async def post(activity_id: UUID, location_id: UUID, request: Request):
    activity = Activity.one(Activity.id == activity_id)
    location = Location.one(Location.id == location_id)

    if activity.creator_id != request.user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="You do not have permission to modify this activity"
        )

    if Activity.first(Activity.location == location, Activity.day == activity.day):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This location is already booked for this day")

    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Payment gateway is down")
