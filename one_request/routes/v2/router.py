from datetime import date, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import users, activities, reviews, locations, groups
from one_request.auth.dependency import RequireApiVersion, OAuth
from one_request.auth.enums import ApiVersion
from ...db.models import Activity
from calendar import monthrange

router = APIRouter(dependencies=[OAuth(RequireApiVersion(ApiVersion.V2))])

router.include_router(users.router, prefix="/users")
router.include_router(activities.router, prefix="/activities")
router.include_router(reviews.router, prefix="/reviews")
router.include_router(locations.router, prefix="/locations")
router.include_router(groups.router, prefix="/groups")


class CalendarDay(BaseModel):
    date: date
    activities: list[Activity] = Field(default_factory=list)


@router.get(
    "/calendar",
    tags=["Activities"],
    response_model=list[CalendarDay],
    summary="Get a calendar of upcoming activities",
)
def get_calendar(month: int) -> list[CalendarDay]:
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Invalid month")

    today = date.today()
    if today.month <= month:
        year = today.year
    else:
        year = today.year + 1

    # get number of days in the month
    _, days = monthrange(year, month)

    # group activities by day in dict of datetime.date: list[Activity], including empty days as empty lists
    calendar = {}
    for i in range(1, days + 1):
        calendar[date(year=year, month=month, day=i)] = []

    # Get start/end dates for query
    start = date(year, month, 1)
    end = start + timedelta(days=days)

    activity_list = Activity.all(Activity.day >= start, Activity.day <= end, Activity.group_id == None)
    for activity in activity_list:
        try:
            calendar[activity.day].append(activity)
        except KeyError:
            """This shouldn't happen but does, ignore it"""
            pass

    return [CalendarDay(date=day, activities=act) for day, act in calendar.items()]
