from operator import or_
from uuid import UUID

from fastapi import APIRouter, status, HTTPException
from fastapi_pagination import Page
from pydantic import BaseModel
from starlette.requests import Request

from one_request.db.models import Location, Activity, Review, Weather

router = APIRouter(tags=["Locations"])


@router.get(
    "/",
    response_model=Page[Location],
    status_code=status.HTTP_200_OK,
    summary="Fetch all locations",
)
async def get_locations() -> Page[Location]:
    return Location.paginate(relations=["reviews"])


@router.get(
    "/{location_id}/activities",
    response_model=Page[Activity],
    status_code=status.HTTP_200_OK,
    summary="Fetch all activities at a given location",
)
async def get_activities(location_id: UUID) -> Page[Activity]:
    return Activity.paginate(
        Activity.invite_code is not None, Location.id == location_id, relations=["group", "reviews"]
    )


@router.get(
    "/{location_id}/weather",
    response_model=list[Weather],
    summary="Get the upcoming weather forecasts for a location",
)
def get_calendar(location_id: UUID):
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="weather service failed",
    )
