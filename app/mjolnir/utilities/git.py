# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import os
import shutil
from utilities.command import run_command


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
        run_command(["git", "submodule", "foreach", "--recursive", "git", "reset", "--hard"], cwd=code_dir)
        run_command(["git", "submodule", "foreach", "--recursive", "git", "clean", "-fdx"], cwd=code_dir)

    # Perform Git Checkout
    if ref:
        run_command(["git", "checkout", ref], cwd=code_dir)
        run_command(["git", "submodule", "update", "--init", "--recursive"], cwd=code_dir)
