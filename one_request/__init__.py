import argparse
from pathlib import Path

from cincoconfig import Config
from pydantic import BaseModel
from sqlalchemy import Engine, create_engine

from one_request.logging import setup_logging
from one_request.db import GlobalSession


class AppSettings(BaseModel, arbitrary_types_allowed=True):
    config: Config
    database: Engine


def setup(config_file: Path = None, args: argparse.Namespace = None, args_ignore: list[str] = None) -> AppSettings:
    """Setup application and database"""
    # pylint: disable=import-outside-toplevel
    from one_request.config import config, load_config_file

    # load and validate config
    load_config_file(config, filepath=config_file)

    if args:
        config.cmdline_args_override(args, ignore=args_ignore)

    config.validate()

    # setup logging
    setup_logging(config)

    #
    # setup database
    #
    # connect
    engine = create_engine(config.db.url, echo=config.log.sql)
    # bind session
    GlobalSession.configure(bind=engine)

    return AppSettings(config=config, database=engine)


def run_server(app_settings: AppSettings) -> None:
    # pylint: disable=import-outside-toplevel
    import uvicorn

    uvicorn.run(
        "one_request.app:app",
        host="0.0.0.0",
        reload=app_settings.config.mode == "dev",
        forwarded_allow_ips="*",
        reload_includes=["config.yml", "config.yaml"],
    )


def main() -> None:
    config = setup()
    run_server(config)  # type: ignore
