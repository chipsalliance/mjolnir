# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import sys

COLORS = {
    "red": "\033[91m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "blue": "\033[94m",
    "gold": "\033[1;38;5;220m",
    "bold": "\033[1m",
    "reset": "\033[0m",
}


class Logger:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
            cls._instance.log_file = None
        return cls._instance

    def init(self, log_path):
        self.log_file = open(log_path, "a")

    def write(self, msg, stdout=True, indent=0, color=None):
        if self.log_file:
            self.log_file.write(msg + "\n")
            self.log_file.flush()

        if stdout:
            if color and color in COLORS:
                msg_stdout = f"{COLORS[color]}{msg}{COLORS['reset']}"
            else:
                msg_stdout = msg

            prefix_indent = "\t" * indent
            lines = msg_stdout.split("\n")
            stdout_msg = "\n".join(prefix_indent + line for line in lines)
            sys.stdout.write(stdout_msg + "\n")
            sys.stdout.flush()

    def success(self, msg, stdout=True, indent=1):
        """Helper to write success logs (green, default indent=1)."""
        self.write(msg, stdout=stdout, indent=indent, color="green")

    def error(self, msg, stdout=True, indent=1):
        """Helper to write error logs (red, default indent=1)."""
        self.write(msg, stdout=stdout, indent=indent, color="red")

    def header(self, msg, stdout=True):
        """Helper to write header/welcome logs (gold bold, indent=0)."""
        self.write(msg, stdout=stdout, indent=0, color="gold")


# Single shared instance
logger = Logger()
