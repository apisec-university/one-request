from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.params import Header
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel as PydanticBaseModel
from pydantic import EmailStr
from starlette.requests import Request

from one_request.auth.dependency import OAuth
from one_request.auth.enums import ApiVersion, UserRole
from one_request.auth.hashers import BcryptPasswordHandler
from one_request.auth.jwt import sign_jwt
from one_request.ctf.data import DEFAULT_GROUP
from one_request.db.models import Group, User
from one_request.exceptions import ApiVersionException

router = APIRouter(tags=["OAUTH2"])


class UserRegistration(PydanticBaseModel):
    name: str
    username: EmailStr
    password: str


@router.post(
    "/register",
    response_model=User,
    status_code=status.HTTP_201_CREATED,
    tags=["OAUTH2"],
    summary="Register",
)
async def register(registration: UserRegistration) -> User:
    role = UserRole.USER

    if User.first(User.email == registration.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"user already exists: '{registration.username}'"
        )

    if User.first(User.name == registration.name):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"user with name already exists: '{registration.name}'"
        )

    u = User(
        name=registration.name,
        role=role,
        email=registration.username,
        primary_group_name=DEFAULT_GROUP["name"],
        password=BcryptPasswordHandler.hash(registration.password).hash,
        groups=[Group.one(Group.name == DEFAULT_GROUP["name"])],
    ).save()
    return User.one(User.id == u.id, relations=["groups"])


class AccessTokenResponse(PydanticBaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


@router.post(
    "/token",
    response_model=AccessTokenResponse,
    status_code=status.HTTP_200_OK,
    tags=["OAUTH2"],
    summary="Retrieve an access token",
)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    # we could expose this as an enum, but more challenge to find version from error messages
    # x_api_version: Annotated[ApiVersion, Header()] = ApiVersion.V2,
    x_api_version: Annotated[str, Header()] = ApiVersion.V2.value,
) -> AccessTokenResponse:
    user = User.one(User.email == form_data.username)

    if x_api_version != ApiVersion.V2 and user.role == UserRole.USER:
        raise ApiVersionException(user.role, requested_api_version=x_api_version, user_api_version=ApiVersion.V2)

    try:
        if not BcryptPasswordHandler.validate(form_data.password, user.password):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    except Exception as e:
        print('failed to validate user password', e, form_data.password, user.password)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='failed to validate user password') from e

    return AccessTokenResponse(
        access_token=sign_jwt(
            user,
            extra={"api_version": x_api_version},
        )
    )


@router.get(
    "/userinfo",
    response_model=User,
    status_code=status.HTTP_200_OK,
    dependencies=[OAuth()],
)
async def user_info(request: Request) -> User:
    return User.one(User.id == request.user.id, relations=True)
