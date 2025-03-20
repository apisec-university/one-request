from sqlmodel import SQLModel

from one_request.auth.enums import UserRole


class ApiVersionException(Exception):
    """Exception with excessive data exposure"""

    role: UserRole
    requested_api_version: str
    user_api_version: str

    def __init__(self, role: UserRole, requested_api_version: str, user_api_version: str):
        self.role = role
        self.requested_api_version = requested_api_version
        self.user_api_version = user_api_version
        super().__init__("user is not permitted to use this API version")


class ApiRoleException(Exception):
    """Exception with excessive data exposure"""

    role: UserRole

    def __init__(self, role: UserRole, **kwargs):
        self.role = role
        super().__init__(f"user role '{role}' cannot perform this action")


class LegacyResourceReadOnlyException(Exception):
    """Exception with excessive data exposure"""

    resource: SQLModel

    def __init__(self, resource: SQLModel):
        self.resource = resource
        super().__init__(f"resource '{resource.__class__.__name__}' is read-only")


class ResourceNotFound(Exception):
    pass


class ValidationError(Exception):
    pass
