from operator import or_
from uuid import UUID

from fastapi import APIRouter, status, HTTPException
from fastapi_pagination import Page
from pydantic import BaseModel
from starlette.requests import Request

from one_request.db.models import Location, Activity, Review

router = APIRouter(tags=["Reviews"])


class ReviewIn(BaseModel):
    rating: int
    review: str


@router.get(
    "/{item_id}",
    response_model=Page[Review],
    status_code=status.HTTP_200_OK,
    summary="Fetch all reviews for a given location or activity id",
)
async def get(item_id: UUID) -> Page[Review]:
    return Review.paginate(
        or_(Review.location_id == item_id, Review.activity_id == item_id),
        relations=[Location, Activity],
    )


@router.post(
    "/{item_id}",
    response_model=Review,
    status_code=status.HTTP_200_OK,
    summary="Create a reviews for a given Activity or Location ID",
)
async def post(item_id: UUID, data: ReviewIn, request: Request) -> Review:
    activity, location = Activity.first(Activity.id == item_id), Location.first(Location.id == item_id)
    activity_id = location_id = None

    if activity:
        activity_id = activity.id
    elif location:
        location_id = location.id
    else:
        raise HTTPException(status_code=404, detail="Item not found")

    return Review(
        rating=data.rating,
        review=data.review,
        location_id=location_id,
        activity_id=activity_id,
        name=request.user.name,
        user_id=request.user.id,
    ).save()
