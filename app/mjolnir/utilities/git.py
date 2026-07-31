# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import os
import shutil
from pathlib import Path

from security.path_sanitizer import resolve_workspace_path
from utilities.command import CommandRunner, run_command
from utilities.logger import logger


def setup_repository(repo_url: str, code_dir: str, ref: str, workspace_dir: str):
    """Clones the target repository if missing, otherwise cleans it, and checks out the requested ref."""
    Path(workspace_dir).mkdir(parents=True, exist_ok=True)

    # Perform Git Clone if missing or corrupt
    code_path = Path(code_dir)
    git_dir = code_path / ".git"
    if not git_dir.exists():
        if code_path.exists():
            shutil.rmtree(code_path)
        run_command(["git", "clone", "--recurse-submodules", repo_url, code_dir])
    else:
        run_command(["git", "fetch", "--all"], cwd=code_dir)
        run_command(["git", "reset", "--hard"], cwd=code_dir)
        run_command(["git", "clean", "-fdx"], cwd=code_dir)
        run_command(
            ["git", "submodule", "foreach", "--recursive", "git", "reset", "--hard"],
            cwd=code_dir,
        )
        run_command(
            ["git", "submodule", "foreach", "--recursive", "git", "clean", "-fdx"],
            cwd=code_dir,
        )

    # Perform Git Checkout
    if ref:
        run_command(["git", "checkout", ref], cwd=code_dir)
        run_command(["git", "submodule", "update", "--init", "--recursive"], cwd=code_dir)

    return get_head_commit(code_dir)


def get_head_commit(code_dir: str) -> str:
    """Returns the current HEAD commit hash for code_dir, or 'unknown' on error."""
    try:
        cmd = ["git", "rev-parse", "HEAD"]
        success, output = CommandRunner(cmd, cwd=code_dir, timeout_sec=5.0).execute()
        if success and output:
            return output
        logger.warning(
            f"Could not determine HEAD commit. Failed to call git rev-parse: {output}. "
            f"Are you in a valid git workspace at '{code_dir}'?"
        )
        return "unknown"
    except Exception as e:
        logger.warning(
            f"Could not determine HEAD commit. Exception occurred while calling git rev-parse: {e}. "
            f"Check if git is installed and '{code_dir}' exists."
        )
        return "unknown"


def is_binary_file(file_path: str) -> bool:
    """Returns True if the file contains binary data (e.g. NUL bytes), False if text."""
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(8192)
            return b"\x00" in chunk
    except Exception:
        return True


def get_diff_files(code_dir: str, base_ref: str, head_ref: str = "HEAD") -> list[str]:
    """Returns a list of relative paths for modified/added text files between base_ref and head_ref."""
    try:
        # Exclude deleted files using --diff-filter=d
        cmd = [
            "git",
            "diff",
            "--name-only",
            "--diff-filter=d",
            base_ref,
            head_ref,
        ]
        success, output = CommandRunner(cmd, cwd=code_dir, timeout_sec=10.0).execute()
        if not success or not output.strip():
            # Fallback to single base_ref comparison if two-ref fails
            cmd_fallback = [
                "git",
                "diff",
                "--name-only",
                "--diff-filter=d",
                base_ref,
            ]
            success, output = CommandRunner(cmd_fallback, cwd=code_dir, timeout_sec=10.0).execute()

        if not success or not output.strip():
            return []

        candidates = [line.strip() for line in output.splitlines() if line.strip()]
        valid_text_files = []

        for rel_path in candidates:
            try:
                safe_path = resolve_workspace_path(rel_path, base_dir=code_dir)
                if safe_path.is_file() and not is_binary_file(str(safe_path)):
                    valid_text_files.append(rel_path)
            except ValueError:
                continue
        return valid_text_files
    except Exception as e:
        logger.error(f"Error executing git diff between '{base_ref}' and '{head_ref}': {e}")
        return []


class GitOperation:
    """Encapsulates Git operations such as listing tracked/untracked candidate files."""

    def __init__(self, directory: str | os.PathLike, respect_git_ignore: bool = True):
        self.directory = Path(directory)
        self.respect_git_ignore = respect_git_ignore

    def list_files(self) -> list[str]:
        """Lists candidate files using git ls-files when respect_git_ignore is True, or directory walk when False."""
        is_file = self.directory.is_file()
        if is_file:
            cwd_path = str(self.directory.parent)
            target_name = self.directory.name
            path_args = ["--", target_name]
        else:
            cwd_path = str(self.directory)
            target_name = None
            path_args = []

        if self.respect_git_ignore:
            cmd = ["git", "ls-files", "-c", "-o", "--exclude-standard"] + path_args
            _, output = CommandRunner(cmd, cwd=cwd_path, timeout_sec=5.0).execute()
            lines = [line for line in output.splitlines() if line]
            return lines if not is_file else ([target_name] if lines else [])

        if is_file:
            return [target_name]

        files: list[str] = []
        for root, _, filenames in os.walk(self.directory):
            root_path = Path(root)
            for filename in filenames:
                file_path = root_path / filename
                rel_path = str(file_path.relative_to(self.directory))
                files.append(rel_path)
        return files
