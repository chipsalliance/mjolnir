# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import os
import shutil
from utilities.command import CommandRunner, run_command
from utilities.logger import logger


def setup_repository(repo_url: str, code_dir: str, ref: str, workspace_dir: str):
    """Clones the target repository if missing, otherwise cleans it, and checks out the requested ref."""
    os.makedirs(workspace_dir, exist_ok=True)

    # Perform Git Clone if missing or corrupt
    git_dir = os.path.join(code_dir, ".git")
    if not os.path.exists(git_dir):
        if os.path.exists(code_dir):
            shutil.rmtree(code_dir)
        run_command(["git", "clone", "--recurse-submodules", repo_url, code_dir])
    else:
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
        run_command(
            ["git", "submodule", "update", "--init", "--recursive"], cwd=code_dir
        )

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


class GitOperation:
    """Encapsulates Git operations such as listing tracked/untracked candidate files."""

    def __init__(self, directory: str | os.PathLike, respect_git_ignore: bool = True):
        self.directory = str(directory)
        self.respect_git_ignore = respect_git_ignore

    def list_files(self) -> list[str]:
        """Lists candidate files using git ls-files when respect_git_ignore is True, or directory walk when False."""
        is_file = os.path.isfile(self.directory)
        if is_file:
            cwd_path = os.path.dirname(self.directory)
            target_name = os.path.basename(self.directory)
            path_args = ["--", target_name]
        else:
            cwd_path = self.directory
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
            for filename in filenames:
                rel_path = os.path.relpath(os.path.join(root, filename), self.directory)
                files.append(rel_path)
        return files
