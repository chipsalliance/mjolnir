# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Standard logging module with ANSI color formatting for Mjolnir.

Console Streams:
- sys.stdout: Receives INFO level messages (headers, success notices, standard progress).
- sys.stderr: Receives WARNING, ERROR, and CRITICAL level messages.

File Stream:
- job.log (if configured): Receives DEBUG level and above with ISO timestamps for deep troubleshooting.
"""

import logging
import sys
from typing import Optional

COLORS = {
    "red": "\033[91m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "orange": "\033[38;5;214m",
    "blue": "\033[94m",
    "gold": "\033[1;38;5;220m",
    "bold": "\033[1m",
    "reset": "\033[0m",
}


class ColoredFormatter(logging.Formatter):
    """Formats log records with ANSI colors based on log level or custom color attribute."""

    LEVEL_COLORS = {
        logging.DEBUG: COLORS["blue"],
        logging.INFO: COLORS["reset"],
        logging.WARNING: COLORS["orange"],
        logging.ERROR: COLORS["red"],
        logging.CRITICAL: COLORS["bold"] + COLORS["red"],
    }

    def format(self, record: logging.LogRecord) -> str:
        color = getattr(record, "color", self.LEVEL_COLORS.get(record.levelno, COLORS["reset"]))
        prefix = COLORS.get(color, color) if color else ""
        suffix = COLORS["reset"] if color else ""
        msg = super().format(record)
        return f"{prefix}{msg}{suffix}"


class MaxLevelFilter(logging.Filter):
    """Filter that only allows log records up to a specified maximum level."""

    def __init__(self, max_level: int):
        super().__init__()
        self.max_level = max_level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno <= self.max_level


class MjolnirLogger(logging.Logger):
    """Standard logging.Logger with convenience formatting methods."""

    def header(self, msg: str):
        self.info(msg, extra={"color": "gold"})

    def success(self, msg: str):
        self.info(msg, extra={"color": "green"})

    def init(self, log_path: Optional[str] = None):
        setup_logger(log_path)


def setup_logger(log_path: Optional[str] = None) -> MjolnirLogger:
    """Configures and returns the application logger."""
    logging.setLoggerClass(MjolnirLogger)
    logger_instance = logging.getLogger("mjolnir")
    logger_instance.setLevel(logging.DEBUG)
    logger_instance.handlers.clear()

    # stdout Handler with ANSI colors (INFO level only)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    stdout_handler.addFilter(MaxLevelFilter(logging.INFO))
    stdout_handler.setFormatter(ColoredFormatter("%(message)s"))
    logger_instance.addHandler(stdout_handler)

    # stderr Handler with ANSI colors (WARNING, ERROR, CRITICAL levels)
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(ColoredFormatter("%(message)s"))
    logger_instance.addHandler(stderr_handler)

    # File Handler if log_path is provided (DEBUG level and above)
    if log_path:
        file_handler = logging.FileHandler(log_path, mode="a")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger_instance.addHandler(file_handler)

    return logger_instance


logger: MjolnirLogger = setup_logger()
