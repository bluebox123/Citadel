"""Structured JSON logging configuration."""

from __future__ import annotations

import logging
import logging.config


def configure_logging(level: str = "INFO") -> None:
    """
    Configure the root logger with a compact, structured formatter.

    Uvicorn's own access logger is left intact; only the application
    namespace and root are reconfigured here.
    """
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "format": (
                        '{"time":"%(asctime)s","level":"%(levelname)s",'
                        '"logger":"%(name)s","msg":%(message)r}'
                    ),
                    "datefmt": "%Y-%m-%dT%H:%M:%S",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "json",
                    "stream": "ext://sys.stdout",
                }
            },
            "root": {"handlers": ["console"], "level": level},
            # Keep uvicorn's loggers at their default level.
            "loggers": {
                "uvicorn": {"propagate": True},
                "uvicorn.error": {"propagate": True},
                "uvicorn.access": {"propagate": True},
            },
        }
    )
