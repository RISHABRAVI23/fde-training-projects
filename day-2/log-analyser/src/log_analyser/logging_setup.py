"""Structured logging: one JSON object per line, written to stderr.

Usage in other modules:
    log = logging.getLogger("log_analyser")
    log.info("analysis_done", extra={"fields": {"lines": 3003, "malformed": 3}})

The message is the EVENT NAME; any details go in extra={"fields": {...}}.
"""
import json
import logging
import sys
from datetime import datetime, timezone

LOGGER_NAME = "log_analyser"


class JsonFormatter(logging.Formatter):
    """Format each log record as a single line of JSON."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "time": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(timespec="seconds"),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        entry.update(getattr(record, "fields", {}))      # details passed via extra={"fields": {...}}
        if record.exc_info:                              # log.exception(...) attaches the traceback
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)            # default=str: e.g. a Path becomes its text


def configure_logging(level: str = "WARNING") -> logging.Logger:
    """Send this package's logs to stderr as JSON, at the given level. Safe to call more than once."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    logger.handlers.clear()                 # calling twice must not create duplicate output
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.propagate = False                # don't ALSO pass records to the root logger
    return logger
