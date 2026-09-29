"""Logging configuration for the ``app`` logger namespace.

Only the application's own loggers are configured here; Uvicorn keeps control of
its server/access loggers.
"""

import logging.config

from app.core.config import LogLevel

LOG_FORMAT = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"


def configure_logging(level: LogLevel = "INFO") -> None:
    """Configure structured-ish, single-line logging to stdout for ``app.*`` loggers."""
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"standard": {"format": LOG_FORMAT}},
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "standard",
                    "stream": "ext://sys.stdout",
                }
            },
            "loggers": {
                "app": {"handlers": ["console"], "level": level, "propagate": False},
            },
        }
    )
