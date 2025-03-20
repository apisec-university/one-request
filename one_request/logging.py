import json
import sys
from functools import lru_cache
from logging import DEBUG, Formatter, Logger, LogRecord, StreamHandler, getLogger
from typing import Any

from cincoconfig import Schema

_logger = getLogger(__name__)


class JsonFormatter(Formatter):
    """
    Formatter that outputs JSON strings after parsing the LogRecord.
    Modified from: https://stackoverflow.com/a/70223539/2834742

    @param dict fmt_dict: Key: logging format attribute pairs. Defaults to {"message": "message"}.
    @param str time_format: time.strftime() format string. Default: "%Y-%m-%dT%H:%M:%S"
    @param str msec_format: Microsecond formatting. Appended at the end. Default: "%s.%03dZ"
    """

    def __init__(
        self,
        fmt_dict: dict = None,
        time_format: str = "%Y-%m-%dT%H:%M:%S",
        msec_format: str = "%s.%03dZ",
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.fmt_dict = fmt_dict if fmt_dict is not None else {"message": "message"}
        self.default_time_format = time_format
        self.default_msec_format = msec_format

    def usesTime(self) -> bool:
        """
        Overwritten to look for the attribute in the format dict values instead of the fmt string.
        """
        return "asctime" in self.fmt_dict.values()

    def formatMessage(self, record: LogRecord) -> str:
        """
        Overwritten to dump LogRecord attributes as a json str.
        KeyError is raised if an unknown attribute is provided in the fmt_dict.
        """
        record.message = record.getMessage()

        if self.usesTime():
            record.asctime = self.formatTime(record, self.datefmt)

        message_dict = {fmt_key: record.__dict__[fmt_val] for fmt_key, fmt_val in self.fmt_dict.items()}
        if record.exc_info:
            # Cache the traceback text to avoid converting it multiple times
            # (it's constant anyway)
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)

        if record.exc_text:
            message_dict["exc_info"] = record.exc_text

        if record.stack_info:
            message_dict["stack_info"] = self.formatStack(record.stack_info)

        return json.dumps(message_dict, default=str)


def get_root_logger() -> Logger:
    return getLogger(__name__.split(".", maxsplit=1)[0])


@lru_cache(maxsize=1)  # only execute this function once
def setup_logging(config: Schema) -> None:
    """Set the log level for the logger."""
    root_logger = get_root_logger()
    # always set root logger to debug, let handlers filter their own messages
    root_logger.setLevel(DEBUG)

    # console handler
    console_handler = StreamHandler(sys.stderr if config.log.stream == "stderr" else sys.stdout)
    console_handler.setLevel(config.log.level)

    if config.log.format == "json":
        formatter = JsonFormatter(
            {"level": "levelname", "message": "message", "loggerName": "name", "timestamp": "asctime"}
        )
        console_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)
    _logger.info(f"console logs set to {config.log.level} as {config.log.format} on {config.log.stream}")
