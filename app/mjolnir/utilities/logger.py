# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Standard logging module with ANSI color formatting for Mjolnir."""

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
        color = getattr(
            record, "color", self.LEVEL_COLORS.get(record.levelno, COLORS["reset"])
        )
        prefix = COLORS.get(color, color) if color else ""
        suffix = COLORS["reset"] if color else ""
        msg = super().format(record)
        return f"{prefix}{msg}{suffix}"


class MjolnirLogger(logging.Logger):
    """Standard logging.Logger with convenience formatting methods."""

    def write(
        self,
        msg: str,
        stdout: bool = True,
        indent: int = 0,
        color: Optional[str] = None,
    ):
        prefix_indent = "\t" * indent
        indented_msg = "\n".join(prefix_indent + line for line in msg.split("\n"))
        self.info(indented_msg, extra={"color": color})

    def header(self, msg: str):
        self.info(msg, extra={"color": "gold"})

    def success(self, msg: str, indent: int = 1):
        prefix_indent = "\t" * indent
        indented_msg = "\n".join(prefix_indent + line for line in msg.split("\n"))
        self.info(indented_msg, extra={"color": "green"})


def setup_logger(log_path: Optional[str] = None) -> MjolnirLogger:
    """Configures and returns the application logger."""
    logging.setLoggerClass(MjolnirLogger)
    logger_instance = logging.getLogger("mjolnir")
    logger_instance.setLevel(logging.INFO)
    logger_instance.handlers.clear()

    # Console Handler with ANSI colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ColoredFormatter("%(message)s"))
    logger_instance.addHandler(console_handler)

    # File Handler if log_path is provided
    if log_path:
        file_handler = logging.FileHandler(log_path, mode="a")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )
        logger_instance.addHandler(file_handler)

    return logger_instance


logger: MjolnirLogger = setup_logger()
