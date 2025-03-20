import logging
from typing import Callable, Generic, List, Literal, Optional, TypeVar

from fastapi import Depends, HTTPException, Request
from fastapi.openapi.models import OAuth2, OAuthFlowPassword, OAuthFlows
from fastapi.security.base import SecurityBase
from sqlalchemy import inspect
from starlette import status

from one_request.auth.enums import UserRole, ApiVersion
from one_request.config import config
from one_request.db.models import User, UserGroupLink, Group
from one_request.exceptions import ApiVersionException

logger = logging.getLogger(__name__)
T = TypeVar("T")
ParamLocationT = Literal["path_params"] | Literal["headers"] | Literal["query_params"]
CastT = Callable[[T | str], T]


class RequireBase(Generic[T]):
    """Generic helper class to represent a dependency based on the requested resource"""

    #: Name of the parameter
    param: str
    #: Location of the parameter
    location: ParamLocationT = "path_params"
    #: Function accepting one argument, the parameter data, and returning the object to check for equality.
    cast: Optional[CastT] = None

    # redefine init to allow for param as a positional argument
    def __init__(self, param: str, location: ParamLocationT = None, cast: CastT = None):
        self.param = param
        if location:
            self.location = location
        if cast:
            self.cast = cast

    def parse(self, request: Request, item_override: T = None) -> T | None:
        # attempt to get and cast data; ignore malformed data and other exceptions
        data = item_override or request.get(self.location, {}).get(self.param)
        logger.debug(f"required parameter: {self.location}[{self.param}]={data}")
        if not data:
            # this solves a bug of, for example, calling ObjectId(None) and producing a new ID
            return None
        try:
            return self.cast(data) if self.cast else data
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    def __str__(self) -> str:
        return f"{self.__class__.__name__}:{self.location}[{self.param}]"

    def check(self, request: Request, item_override: str = None) -> bool:
        """Return true if the request is valid, false if it's not."""
        raise NotImplementedError()


class RequireSelf(RequireBase):
    """Require the resource being request is a user, and belongs to the same organization as the current user"""

    cast: Callable = inspect(User).c.id.type.python_type

    def check(self, request: Request, item_override: str = None) -> bool:
        data = self.parse(request, item_override)
        if not data:
            return False

        return data == request.user.id


class RequireApiVersion(RequireBase):
    """Require the resource being request is a user, and belongs to the same organization as the current user"""

    version: ApiVersion

    def __init__(self, version: str | ApiVersion):
        self.version = ApiVersion(version)
        super().__init__("authorization", location="headers", cast=ApiVersion)

    def parse(self, request: Request, item_override: T = None) -> T | None:
        """Disable parse step, we need to read from the JWT"""

    def check(self, request: Request, item_override: str = None) -> bool:
        if not request.user.api_version == self.version:
            raise ApiVersionException(
                request.user.role,
                requested_api_version=self.version,
                user_api_version=request.user.api_version,
            )
        return True


class RequireGroupByName(RequireBase):
    """Require the requested parameter be a group ID that the user belongs to"""

    def check(self, request: Request, item_override: str = None) -> bool:
        data = self.parse(request, item_override)
        if not data:
            return False
        group = Group.one(Group.name == data)
        if not group:
            logger.debug(f"RequireGroupByName: group not found: {data}")
            return False

        return UserGroupLink.exists(
            UserGroupLink.group_id == group.id,
            UserGroupLink.user_id == request.user.id,
        )


PermissionRequirements = UserRole | RequireBase | List[UserRole | RequireBase]


class PermissionDependency(SecurityBase):
    """Require any of requirements to be met to access the resource."""

    requirements: List[UserRole | RequireBase]

    def __init__(self, requirements: PermissionRequirements | None, scheme_name: str = "OAuth2"):
        self.requirements = []
        self.scheme_name = scheme_name

        if requirements:
            # this if handles when no roles are defined, otherwise we end up with a list containing [None]
            self.requirements = requirements if isinstance(requirements, list) else [requirements]

        self.model = OAuth2(
            description="Login with username and password",
            flows=OAuthFlows(password=OAuthFlowPassword(tokenUrl=config.auth.token_url)),
        )

    async def __call__(self, request: Request) -> None:
        if not request.user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user is not logged in")

        if not self.requirements:
            # No roles were specified, just require a user is logged in
            return

        for req in self.requirements:
            if isinstance(req, RequireBase):
                if req.check(request):
                    logger.debug(f"access permitted via {req}")
                    return
            elif isinstance(req, UserRole) and request.user.role == req:
                # if a user has a required role, they're authorized
                logger.debug(f"access permitted via role={req}")
                return

        logger.debug(f"access denied {' OR '.join(str(r) for r in self.requirements)}")
        # no roles matched, user does not have permission
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="user does not have permission to access this resource"
        )


# pylint: disable=invalid-name
def OAuth(requirements: PermissionRequirements = None) -> Depends:  # type: ignore[valid-type]
    return Depends(PermissionDependency(requirements))
