# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import os
import shutil
from utilities.command import run_command, run_command_capture


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


class GitOperation:
    """Encapsulates Git operations such as listing tracked/untracked candidate files."""

    def __init__(self, directory: str | os.PathLike, respect_git_ignore: bool = True):
        self.directory = str(directory)
        self.respect_git_ignore = respect_git_ignore

    def list_files(self) -> list[str]:
        """Lists candidate files using git ls-files when respect_git_ignore is True, or directory walk when False."""
        if os.path.isfile(self.directory):
            target_name = os.path.basename(self.directory)
            cwd_path = os.path.dirname(self.directory)
            if self.respect_git_ignore:
                res = run_command_capture(
                    [
                        "git",
                        "ls-files",
                        "-c",
                        "-o",
                        "--exclude-standard",
                        "--",
                        target_name,
                    ],
                    cwd=cwd_path,
                    timeout=5.0,
                )
                return [target_name] if res.stdout.strip() else []
            return [target_name]

        if self.respect_git_ignore:
            res = run_command_capture(
                ["git", "ls-files", "-c", "-o", "--exclude-standard"],
                cwd=self.directory,
                timeout=5.0,
            )
            return res.stdout.splitlines()

        files: list[str] = []
        for root, _, filenames in os.walk(self.directory):
            for filename in filenames:
                rel_path = os.path.relpath(os.path.join(root, filename), self.directory)
                files.append(rel_path)
        return files
