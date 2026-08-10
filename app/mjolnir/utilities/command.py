# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import asyncio
from pathlib import Path
import subprocess
import sys
from google.cloud import storage
from utilities.logger import logger


def run_command(args, cwd=None, env=None):
    """Executes a shell command cleanly without rolling console windows."""
    logger.debug(f"Executing: {' '.join(args)} in {cwd or '.'}")

    p = subprocess.Popen(
        args,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,  # Line buffered
    )

    output_lines = []

    while True:
        line = p.stdout.readline()
        if not line and p.poll() is not None:
            break

        if line:
            output_lines.append(line)
            logger.debug(line.rstrip("\r\n"))

    rc = p.wait()
    cmd_str = " ".join(args) if isinstance(args, list) else str(args)

    if rc == 0:
        logger.success(f"Command succeeded: '{cmd_str}'")
    else:
        logger.error(f"Command failed with exit code {rc}: '{cmd_str}'")

        for line in output_lines:
            sys.__stderr__.write(line)
        sys.__stderr__.flush()
        sys.exit(rc)


def run_command_capture(
    args: list[str],
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    check: bool = False,
    timeout: float | None = None,
) -> subprocess.CompletedProcess:
    """Executes a command and returns CompletedProcess object.
    Logs execution and output to the logger.
    If check=True and command fails, exits the program.
    """
    logger.debug(f"Executing: {' '.join(args)} in {cwd or '.'}")
    try:
        res = subprocess.run(
            args,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if res.stdout:
            for line in res.stdout.splitlines():
                logger.debug(line)
        if res.stderr:
            for line in res.stderr.splitlines():
                logger.debug(line)

        cmd_str = " ".join(args) if isinstance(args, list) else str(args)
        if res.returncode == 0:
            logger.debug(f"Command succeeded: '{cmd_str}'")
        else:
            if check:
                logger.error(f"Command failed with exit code {res.returncode}: '{cmd_str}'")
                sys.__stderr__.write(res.stderr)
                sys.__stderr__.flush()
                sys.exit(res.returncode)

        return res
    except Exception as e:
        cmd_str = " ".join(args) if isinstance(args, list) else str(args)
        logger.debug(f"Command '{cmd_str}' failed with exception: {e}")
        if check:
            logger.error(f"Command '{cmd_str}' failed with exception: {e}")
            sys.exit(1)
        raise e


class CommandRunner:
    """Encapsulates CLI execution, logging, return code checks, and error formatting."""

    def __init__(
        self,
        args: list[str],
        cwd: str | Path | None = None,
        timeout_sec: float | None = 5.0,
        env: dict[str, str] | None = None,
    ) -> None:
        self.args = args
        self.cwd = str(cwd) if cwd is not None else None
        self.timeout_sec = timeout_sec
        self.env = env

    def execute(self) -> tuple[bool, str]:
        """Executes CLI command and returns (success_flag, output_or_error_string)."""
        try:
            res = run_command_capture(
                self.args, cwd=self.cwd, env=self.env, timeout=self.timeout_sec
            )
        except Exception as e:
            return False, f"Error executing {self.args[0]}: {e}"

        if res.returncode != 0 and not res.stdout:
            err_msg = res.stderr.strip() or f"Process exited with code {res.returncode}"
            return False, f"Error executing {self.args[0]}: {err_msg}"
        return True, res.stdout.strip()

    async def execute_async(self) -> tuple[bool, str]:
        """Asynchronously executes CLI command and returns (success_flag, output_or_error_string)."""
        return await asyncio.to_thread(self.execute)
