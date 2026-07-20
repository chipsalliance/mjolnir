# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import subprocess
import sys
from google.cloud import storage
from utilities.logger import logger


def run_command(args, cwd=None, env=None):
    """Executes a shell command.
    While running, it shows a rolling console window of the last 10 lines of output.
    On success, the rolling window is cleared and "Command succeeded." is printed.
    On failure, the rolling window is cleared and the full output is dumped to stderr.
    """
    logger.write(f"Executing: {' '.join(args)} in {cwd or '.'}")

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
    window_size = 10
    rolling_lines = []
    prev_printed = 0
    is_tty = sys.__stdout__.isatty()

    while True:
        line = p.stdout.readline()
        if not line and p.poll() is not None:
            break

        if line:
            output_lines.append(line)
            # Log line output to file only
            logger.write(line.rstrip("\r\n"), stdout=False)

            # Rolling console window
            if is_tty:
                # Strip newline for rolling window display
                rolling_lines.append(line.rstrip("\r\n"))
                display_lines = rolling_lines[-window_size:]

                # Move cursor up and clear
                if prev_printed > 0:
                    sys.__stdout__.write(f"\r\033[{prev_printed}A\033[J")

                # Print rolling lines
                for l in display_lines:
                    sys.__stdout__.write(l + "\n")
                sys.__stdout__.flush()
                prev_printed = len(display_lines)

    rc = p.wait()

    # Clear the rolling window from the terminal
    if is_tty and prev_printed > 0:
        sys.__stdout__.write(f"\r\033[{prev_printed}A\033[J")
        sys.__stdout__.flush()

    if rc == 0:
        logger.success("Execution succeeded")
    else:
        logger.error(f"Execution failed with exit code: {rc}")

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
    logger.write(f"Executing: {' '.join(args)} in {cwd or '.'}", stdout=False)
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
                logger.write(line, stdout=False)
        if res.stderr:
            for line in res.stderr.splitlines():
                logger.write(line, stdout=False)

        if res.returncode == 0:
            logger.success("Execution succeeded.", indent=0)
        else:
            if check:
                logger.error(f"Execution failed with exit code: {res.returncode}.")
                sys.__stderr__.write(res.stderr)
                sys.__stderr__.flush()
                sys.exit(res.returncode)

        return res
    except Exception as e:
        logger.error(f"Execution failed with exception: {e}.")
        if check:
            sys.exit(1)
        raise e
