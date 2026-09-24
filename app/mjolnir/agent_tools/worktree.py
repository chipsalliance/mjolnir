# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Isolated workspace sandbox tools for Proof-of-Concept synthesis and test harness execution."""

from google.adk.tools import ToolContext

from constants import HARNESS_COMMAND_TIMEOUT_SECONDS
from security.path_sanitizer import resolve_workspace_path
from utilities.decorators import limit_tool_output
from utilities.logger import logger
from utilities.worktree_sandbox import current_worktree_sandbox


def _get_active_sandbox():
    sandbox = current_worktree_sandbox.get()
    if sandbox is None:
        raise RuntimeError("Sandbox tool invoked outside of an active WorktreeSandbox context.")
    return sandbox


@limit_tool_output
async def patch_worktree_file(
    file_path: str,
    target_content: str,
    replacement_content: str,
    tool_context: ToolContext | None = None,
) -> str:
    """Patches an existing file in the isolated PoC sandbox by replacing an exact text block.

    Use this tool to insert a new unit test or harness case into an existing test module or
    build file without rewriting the entire file. Remember that modifying production code to
    artificially trigger a vulnerability will cause your PoC to be rejected during Final Review.

    Args:
        file_path: Relative path to the file within the sandbox.
        target_content: Exact substring in the file to replace (include surrounding lines of context
            so the match is unique).
        replacement_content: New text replacing `target_content`.

    Returns:
        Confirmation message with the updated line count, or an error if `target_content` did not match.
    """
    try:
        sandbox = _get_active_sandbox()
        safe_path = resolve_workspace_path(file_path, base_dir=str(sandbox.worktree_dir))
    except Exception as err:
        return f"Error: {err}"

    if not safe_path.exists() or not safe_path.is_file():
        return f"Error: File '{file_path}' does not exist in the sandbox."

    rel_path = str(safe_path.relative_to(sandbox.worktree_dir))
    current_text = safe_path.read_text(encoding="utf-8", errors="replace")

    count = current_text.count(target_content)
    if count == 0:
        return (
            f"Error: `target_content` was not found in '{rel_path}'. Use `read_file` to check the "
            "exact lines and whitespace before calling `patch_worktree_file`."
        )
    if count > 1:
        return (
            f"Error: `target_content` matched {count} locations in '{rel_path}'. Include more "
            "surrounding lines in `target_content` to uniquely identify the target location."
        )

    new_text = current_text.replace(target_content, replacement_content, 1)
    sandbox.write_file(rel_path, new_text)
    logger.debug(f"[Tool Execution] patch_worktree_file: updated {rel_path}")
    return f"Successfully patched '{rel_path}' in sandbox ({len(new_text.splitlines())} lines)."


@limit_tool_output
async def write_worktree_file(
    file_path: str,
    content: str,
    tool_context: ToolContext | None = None,
) -> str:
    """Creates or overwrites a file inside the isolated PoC sandbox.

    Use this tool when creating a new standalone test file or harness script. For editing an
    existing large file, prefer `patch_worktree_file` instead.

    Args:
        file_path: Relative path to the file in the sandbox.
        content: Complete file content to write.

    Returns:
        Confirmation message with the written line count.
    """
    try:
        sandbox = _get_active_sandbox()
        safe_path = resolve_workspace_path(file_path, base_dir=str(sandbox.worktree_dir))
    except Exception as err:
        return f"Error: {err}"

    rel_path = str(safe_path.relative_to(sandbox.worktree_dir))
    sandbox.write_file(rel_path, content)
    logger.debug(f"[Tool Execution] write_worktree_file: wrote {rel_path}")
    return f"Successfully wrote '{rel_path}' in sandbox ({len(content.splitlines())} lines)."


@limit_tool_output
async def run_harness_command(
    command: str,
    timeout_seconds: int = HARNESS_COMMAND_TIMEOUT_SECONDS,
    tool_context: ToolContext | None = None,
) -> str:
    """Executes a compilation or unit-test command inside the isolated PoC sandbox.

    Always scope test execution tightly to the specific target package/binary and test filter
    supported by the project's build system so compilation and execution complete quickly.

    Args:
        command: Shell command to run from the sandbox root.
        timeout_seconds: Maximum execution time in seconds (default 900s).

    Returns:
        Formatted exit status and combined stdout/stderr from the command execution.
    """
    try:
        sandbox = _get_active_sandbox()
    except Exception as err:
        return f"Error: {err}"

    logger.info(f"      [PoC Sandbox] Executing: {command}")
    record = await sandbox.run_harness_command_async(
        command=command, timeout_seconds=timeout_seconds
    )
    return f"Command: {record.command}\nExit Code: {record.returncode}\nOutput:\n{record.output}"


@limit_tool_output
async def get_worktree_diff(
    tool_context: ToolContext | None = None,
) -> str:
    """Returns the unified diff of all file modifications and additions inside the isolated sandbox.

    Call this tool before concluding to inspect your exact unified diff and verify that only
    unit test / harness code was added or modified and no production code was tampered with.

    Returns:
        Unified diff string, or a message indicating no modifications exist.
    """
    try:
        sandbox = _get_active_sandbox()
    except Exception as err:
        return f"Error: {err}"

    diff_text = sandbox.get_diff()
    if not diff_text.strip():
        return "No modifications currently present in the sandbox."
    return diff_text


@limit_tool_output
async def reset_worktree(
    tool_context: ToolContext | None = None,
) -> str:
    """Resets the isolated PoC sandbox back to its clean baseline state, discarding all edits."""
    try:
        sandbox = _get_active_sandbox()
    except Exception as err:
        return f"Error: {err}"

    return sandbox.reset()
