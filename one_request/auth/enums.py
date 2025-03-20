from enum import Enum


PALANTIR_ROLE = "PALANTIR"


class UserRole(str, Enum):
    ADMIN = "admin"
    STAFF = "staff"
    DELETED = "deleted"
    USER = "user"


class ApiVersion(str, Enum):
    LEGACY = "legacy"
    V2 = "v2"
    PALANTIR_ROLE = "palantir"
