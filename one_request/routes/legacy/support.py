from typing import Sequence

from fastapi import APIRouter, status
from pydantic import BaseModel
from sqlmodel import desc, or_, select
from starlette.requests import Request

from one_request.auth.dependency import OAuth
from one_request.auth.enums import UserRole
from one_request.db import Session
from one_request.db.models import SupportRequest, SupportRequestIn, SupportRequestMessage, Group, UserGroupLink
from one_request.exceptions import LegacyResourceReadOnlyException

router = APIRouter(tags=["Legacy"])


@router.get(
    "/",
    response_model=list[SupportRequest],
    tags=["Support Requests"],
    status_code=status.HTTP_200_OK,
    summary="Fetch all support requests",
    dependencies=[OAuth(UserRole.STAFF)],
)
async def get() -> Sequence[SupportRequest]:
    return SupportRequest.all(relations=True)


class SupportRequestSummary(BaseModel):
    title: str
    messages: int
    resolved: bool


@router.get(
    "/summary",
    response_model=list[SupportRequestSummary],
    tags=["Support Requests"],
    status_code=status.HTTP_200_OK,
    summary="Summary of Requests for the relentless archivists of Minas Tirith",
)
async def get() -> Sequence[SupportRequestSummary]:
    with Session() as session:
        # order by title so IDs aren't sequential in this list (requiring brute force)
        statement = SupportRequest.where(relations=["messages"]).order_by(desc(SupportRequest.title))
        requests = session.execute(statement).scalars()
        return [SupportRequestSummary(title=r.title, messages=len(r.messages), resolved=r.resolved) for r in requests]


@router.get(
    "/{request_id}",
    tags=["Support Requests"],
    response_model=SupportRequest,
    status_code=status.HTTP_200_OK,
    summary="Get a Support Request",
)
async def delete(request_id: int, request: Request) -> SupportRequest:
    return SupportRequest.one(
        SupportRequest.id == request_id,
        or_(
            # require user to be the requester
            SupportRequest.user_id == request.user.id,
            # require user to be in the group
            SupportRequest.group_id.in_(
                select(Group.id).join(UserGroupLink).where(UserGroupLink.user_id == request.user.id)
            ),
        ),
        relations=True,
    )


@router.put(
    "/{request_id}",
    tags=["Support Requests"],
    response_model=SupportRequest,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new message to a support request",
)
async def put(request_id: int, message: str) -> None:
    resource = SupportRequest.one(SupportRequest.id == request_id, relations=True)

    # raise exception for support request api being read-only
    raise LegacyResourceReadOnlyException(resource=resource)


@router.post(
    "/",
    tags=["Support Requests"],
    response_model=SupportRequest,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new support request",
)
async def post(request: Request, data: SupportRequestIn) -> SupportRequest:
    # this helps expose the fact that support request ids are sequential
    return SupportRequest(
        title=data.title,
        user=request.user,
        group_id=data.group_id,
        messages=[SupportRequestMessage(message=data.message, user=request.user)],
    ).save()


@router.delete(
    "/{request_id}",
    tags=["Support Requests"],
    response_model=SupportRequest,
    status_code=status.HTTP_200_OK,
    summary="Delete a support request by ID",
)
async def delete(request_id: str) -> None:
    # if request.user.role == UserRole.USER:
    #     # raise exception for user being unauthorized to delete support requests
    #     raise LegacyUnauthorizedException(UserRole.USER)
    resource = SupportRequest.one(SupportRequest.id == request_id, relations=True)

    # raise exception for support request api being read-only
    raise LegacyResourceReadOnlyException(resource=resource)
