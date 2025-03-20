# pylint: disable=wrong-import-position,wrong-import-order,ungrouped-imports,import-outside-toplevel
"""
This file is used for development of the base application.
App must be run as an import for hot reloads to work in uvicorn.
"""
import traceback

from cincoconfig import Config
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi_pagination import add_pagination
from sqlalchemy import Engine
from sqlalchemy.exc import MultipleResultsFound, NoResultFound, IntegrityError
from starlette import status
from starlette.authentication import AuthenticationError
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from one_request import setup
from one_request.auth.middleware import AuthBackend
from one_request.exceptions import (
    ResourceNotFound,
    ApiVersionException,
    LegacyResourceReadOnlyException,
    ApiRoleException,
)


def add_app_handlers(app_: FastAPI) -> None:
    """Exception handlers"""

    @app_.exception_handler(NoResultFound)
    async def no_result_handler(_r: Request, _exc: NoResultFound) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "Resource not found"},
        )

    @app_.exception_handler(IntegrityError)
    async def no_result_handler(_r: Request, _exc: IntegrityError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": f"Integrity Error: {''.join(_exc.args)}"},
        )

    @app_.exception_handler(ApiVersionException)
    async def legacy_auth_exception(_r: Request, exc: ApiVersionException) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "detail": "Users should use API version v2",
                "exc": traceback.format_exc(),
                "role": exc.role,
                "requested_api_version": exc.requested_api_version,
                "allowed_api_version": exc.user_api_version,
            },
        )

    @app_.exception_handler(ApiRoleException)
    async def legacy_auth_exception(_r: Request, exc: ApiRoleException) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "detail": str(exc),
                # "exc": traceback.format_exc(),
                "role": exc.role,
            },
        )

    @app_.exception_handler(LegacyResourceReadOnlyException)
    async def legacy_auth_exception(_r: Request, exc: LegacyResourceReadOnlyException) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
            content={
                "detail": "Legacy API is deprecated and read only.",
                "exc": traceback.format_exc(),
                "resource": exc.resource.model_dump(mode="json"),
            },
        )

    @app_.exception_handler(ResourceNotFound)
    async def resource_no_found_handler(_r: Request, exc: ResourceNotFound) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc)},
        )

    @app_.exception_handler(MultipleResultsFound)
    async def multiple_results_handler(_r: Request, _exc: MultipleResultsFound) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Multiple results found when one was expected"},
        )

    @app_.exception_handler(AuthenticationError)
    async def unauthorized(_: Request, exc: AuthenticationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": str(exc)},
        )


def add_openapi_override(app_: FastAPI, server=None):
    def custom_openapi():
        if app_.openapi_schema:
            return app_.openapi_schema

        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            openapi_version=app.openapi_version,
            description=app.description,
            routes=app.routes,
        )

        if not openapi_schema.get("components"):
            openapi_schema["components"] = {}

        if server:
            openapi_schema["servers"] = [{"url": server}]
        # set global auth schemes
        openapi_schema["security"] = [{"OAuth2": []}, {"bearerAuth": []}]
        # set available global auth schemes
        openapi_schema["components"]["securitySchemes"] = {
            # provide bearer token auth as an alternative
            "bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"},
            # primary auth method - oauth2 w/ username/password. If only we could make this NOT prompt for client_id/client_secret
            "OAuth2": {
                "type": "oauth2",
                "flows": {
                    "password": {
                        # add server to auth token url if available
                        "tokenUrl": f"{server or ''}/token"
                    },
                },
            },
        }

        # For each path
        for path in openapi_schema["paths"].values():
            for operation in path.values():
                if "security" in operation:
                    # set security to none so that it will default to "inherit from parent" in postman
                    del operation["security"]
                # operation["security"] = None

        app_.openapi_schema = openapi_schema
        return app_.openapi_schema

    app_.openapi = custom_openapi


def create_app(config: Config, database: Engine) -> FastAPI:
    """
    Create API Application
    :param config: Initialized config
    :param database: SQLAlchemy Engine
    :param config: Relevant CincoConfig Configuration object
    :return:
    """
    #
    # setup app
    #
    import one_request.health
    import one_request.routes.v2.router
    import one_request.routes.legacy
    import one_request.routes.oauth
    import one_request.routes.palantir
    import one_request.routes.one_request
    import one_request.routes.validate
    import one_request.routes.ui

    app_ = FastAPI(
        title=config.openapi.name,
        description=config.openapi.description,
        version="0.1.0",
        openapi_url=config.openapi.openapi_url,
        docs_url=config.openapi.docs_url,
        redoc_url=config.openapi.redocs_url,
        # dependencies=[Depends(Logging)],
        middleware=[
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            ),
            Middleware(
                AuthenticationMiddleware,
                backend=AuthBackend(jwt_secret=config.auth.jwt.secret_key, jwt_algorithms=[config.auth.jwt.algorithm]),
                on_error=AuthBackend.on_error,
            ),
        ],
    )

    app_.include_router(router=one_request.routes.oauth.router)
    app_.include_router(router=one_request.routes.legacy.router)
    app_.include_router(prefix="/palantir", router=one_request.routes.palantir.router)
    app_.include_router(router=one_request.routes.one_request.router)
    app_.include_router(router=one_request.routes.validate.router)
    app_.include_router(router=one_request.routes.ui.router)
    app_.include_router(prefix="/v2", router=one_request.routes.v2.router.router)
    # healthz/livez endpoints
    app_.include_router(router=one_request.health.router, include_in_schema=False)
    # add exception handlers
    add_app_handlers(app_)
    # add pagination
    add_pagination(app_)
    add_openapi_override(app_, server=config.openapi.server)
    return app_


settings = setup()
app = create_app(settings.config, settings.database)
