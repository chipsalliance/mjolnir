# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Isolated scratch worktree sandbox for Proof-of-Concept synthesis and verification."""

import asyncio
from contextvars import ContextVar
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess

from constants import (
    BUILD_CONFIGURATION_FILES,
    CARGO_TARGET_CACHE_SUBDIR,
    HARNESS_COMMAND_TIMEOUT_SECONDS,
    POC_ARTIFACTS_SUBDIR,
    POC_WORKTREES_SUBDIR,
    SANDBOX_ALLOWED_ENV_VARS,
    TEST_DIRECTORY_NAMES,
    TEST_FILE_SUFFIXES,
)
from utilities.command import run_command_capture
from utilities.logger import logger


@dataclass
class CommandRecord:
    """Ground-truth record of a command executed inside the sandbox."""

    command: str
    returncode: int
    output: str


current_worktree_sandbox: ContextVar["WorktreeSandbox | None"] = ContextVar(
    "current_worktree_sandbox", default=None
)

REPRODUCE_SCRIPT_TEMPLATE = """#!/usr/bin/env bash
# Standalone Mjolnir PoC Reproducer for {vuln_id}
set -e
SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
if [[ "$1" == "--revert" ]]; then
  cd "${{2:-.}}"
  [[ -f "$SCRIPT_DIR/poc_patch.diff" ]] && patch -R -p1 < "$SCRIPT_DIR/poc_patch.diff" || true
  exit 0
fi
TARGET_DIR="${{1:-.}}"
cd "$TARGET_DIR"

[[ -f "$SCRIPT_DIR/poc_patch.diff" ]] && patch -p1 --forward < "$SCRIPT_DIR/poc_patch.diff"
echo "[Mjolnir PoC] Executing: {last_cmd}"
set +e
{last_cmd}
CMD_EXIT_CODE=$?
set -e
echo "=================================================================="
if [[ $CMD_EXIT_CODE -ne 0 ]]; then
  echo "[Mjolnir PoC] VERDICT: VULNERABILITY REPRODUCED (exit code: $CMD_EXIT_CODE)"
else
  echo "[Mjolnir PoC] VERDICT: COMMAND RETURNED 0"
fi
echo "=================================================================="
exit $CMD_EXIT_CODE
"""


class WorktreeSandbox:
    """Manages an isolated scratch worktree for PoC synthesis and verification."""

    def __init__(
        self,
        source_code_dir: Path,
        workspace_dir: Path,
        vuln_id: str,
        keep_worktree: bool = False,
    ) -> None:
        self.source_code_dir = source_code_dir.resolve()
        self.workspace_dir = workspace_dir.resolve()
        self.vuln_id = vuln_id
        self.keep_worktree = keep_worktree
        self.worktree_dir = self.workspace_dir / POC_WORKTREES_SUBDIR / "scratch"
        self.artifact_dir = self.workspace_dir / POC_ARTIFACTS_SUBDIR / vuln_id
        self.command_history: list[CommandRecord] = []
        self._ctx_token = None

    async def __aenter__(self) -> "WorktreeSandbox":
        await asyncio.to_thread(self.setup)
        self._ctx_token = current_worktree_sandbox.set(self)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._ctx_token is not None:
            current_worktree_sandbox.reset(self._ctx_token)
            self._ctx_token = None
        await asyncio.to_thread(self.cleanup)

    def _run_git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "-C", str(self.worktree_dir), *args],
            capture_output=True,
            text=True,
            check=False,
        )

    def _init_local_git_repo(self) -> None:
        """Copies source tree and initializes a lightweight local git repo for non-git directories."""
        shutil.copytree(self.source_code_dir, self.worktree_dir, symlinks=True, dirs_exist_ok=True)
        for cmd in (
            ["init"],
            ["config", "user.email", "mjolnir@local"],
            ["config", "user.name", "Mjolnir"],
            ["add", "-A"],
            ["commit", "-m", "baseline"],
        ):
            self._run_git(*cmd)

    def setup(self) -> None:
        """Initializes the single scratch worktree and resets it to clean baseline."""
        self.worktree_dir.parent.mkdir(parents=True, exist_ok=True)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.command_history.clear()

        if not self.worktree_dir.exists():
            if (self.source_code_dir / ".git").exists():
                res = subprocess.run(
                    [
                        "git",
                        "-C",
                        str(self.source_code_dir),
                        "worktree",
                        "add",
                        "--detach",
                        "-f",
                        str(self.worktree_dir),
                        "HEAD",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if res.returncode != 0:
                    self._init_local_git_repo()
            else:
                self._init_local_git_repo()

            # Link tags index if present
            src_tags = self.source_code_dir / ".git" / "tags"
            if not src_tags.exists():
                src_tags = self.source_code_dir / ".mjolnir_tags"
            dst_tags = self.worktree_dir / ".mjolnir_tags"
            if src_tags.exists() and not dst_tags.exists():
                try:
                    dst_tags.symlink_to(src_tags)
                except OSError:
                    pass

            # Exclude build caches, tags, and artifact directories from git tracking
            try:
                exclude_path = None
                git_entry = self.worktree_dir / ".git"
                if git_entry.is_dir():
                    exclude_path = git_entry / "info" / "exclude"
                elif git_entry.is_file():
                    content = git_entry.read_text(encoding="utf-8").strip()
                    if content.startswith("gitdir:"):
                        gd = Path(content.split(":", 1)[1].strip())
                        exclude_path = gd / "info" / "exclude"
                if exclude_path:
                    exclude_path.parent.mkdir(parents=True, exist_ok=True)
                    existing = (
                        exclude_path.read_text(encoding="utf-8") if exclude_path.exists() else ""
                    )
                    patterns = [
                        ".mjolnir_tags*",
                        "tags*",
                        "target/",
                        CARGO_TARGET_CACHE_SUBDIR + "/",
                        POC_WORKTREES_SUBDIR + "/",
                        POC_ARTIFACTS_SUBDIR + "/",
                    ]
                    to_add = [p for p in patterns if p not in existing]
                    if to_add:
                        with open(exclude_path, "a", encoding="utf-8") as f:
                            f.write("\n" + "\n".join(to_add) + "\n")
            except Exception:
                pass
        else:
            self.reset()

    def cleanup(self) -> None:
        """Persists unified diff, command execution logs, and reproduce.sh, then resets worktree."""
        try:
            diff_text = self.get_diff()
            if diff_text.strip():
                (self.artifact_dir / "poc_patch.diff").write_text(diff_text, encoding="utf-8")
            if self.command_history:
                log_lines = [
                    f"=== Command #{i}: {r.command} (exit={r.returncode}) ===\n{r.output}\n"
                    for i, r in enumerate(self.command_history, start=1)
                ]
                (self.artifact_dir / "harness_commands.log").write_text(
                    "\n".join(log_lines), encoding="utf-8"
                )
            if diff_text.strip() or self.command_history:
                last_cmd = (
                    self.command_history[-1].command
                    if self.command_history
                    else "echo 'No command recorded'"
                )
                reproduce_script = REPRODUCE_SCRIPT_TEMPLATE.format(
                    vuln_id=self.vuln_id, last_cmd=last_cmd
                )
                reproduce_path = self.artifact_dir / "reproduce.sh"
                reproduce_path.write_text(reproduce_script, encoding="utf-8")
                reproduce_path.chmod(0o755)
        except Exception as err:
            logger.debug(f"Failed to persist PoC artifacts for {self.vuln_id}: {err}")
        finally:
            self.reset()

    def write_file(self, rel_path: str, content: str) -> None:
        """Writes content to a file inside the worktree."""
        target_path = self.worktree_dir / rel_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding="utf-8")

    def get_diff(self) -> str:
        """Computes unified diff across all modified or added files using git."""
        self._run_git("add", "-N", ".")
        res = self._run_git("diff", "HEAD", "--", ":!.mjolnir_tags*", ":!tags*")
        return res.stdout if res.returncode == 0 else ""

    def get_modified_files(self) -> list[str]:
        """Returns list of relative paths for all modified or newly created files."""
        self._run_git("add", "-N", ".")
        res = self._run_git("diff", "--name-only", "HEAD", "--", ":!.mjolnir_tags*", ":!tags*")
        return [line.strip() for line in res.stdout.splitlines() if line.strip()]

    def is_test_or_harness_path(self, rel_path: str) -> bool:
        """Checks if a file path belongs to a test suite or harness/build configuration."""
        p = Path(rel_path.lower())
        if any(p.name.startswith(prefix) for prefix in (".mjolnir_tags", "tags")):
            return True
        if any(part in TEST_DIRECTORY_NAMES for part in p.parts):
            return True
        if any(p.name.endswith(suffix) for suffix in TEST_FILE_SUFFIXES):
            return True
        return p.name in BUILD_CONFIGURATION_FILES

    def has_production_code_modifications(self) -> bool:
        """Returns True if any non-test, non-harness production source file was modified or added."""
        for rel in self.get_modified_files():
            if self.is_test_or_harness_path(rel):
                continue
            # If a source file was modified, verify that no existing baseline lines were removed
            diff = self._run_git("diff", "HEAD", "--", rel).stdout
            if any(
                line.startswith("-") and not line.startswith("---") for line in diff.splitlines()
            ):
                return True
            # In languages like Rust, tests can be inline (e.g. #[cfg(test)] mod tests).
            # If all additions belong to test modules/functions, treat as test code.
            if (
                "#[test]" in diff
                or "#[cfg(test)]" in diff
                or "mod tests" in diff
                or "mod test" in diff
            ):
                continue
            return True
        return False

    def count_removed_baseline_lines(self) -> int:
        """Counts existing baseline lines deleted or modified in non-test production files."""
        prod_files = [f for f in self.get_modified_files() if not self.is_test_or_harness_path(f)]
        if not prod_files:
            return 0
        res = self._run_git("diff", "HEAD", "--", *prod_files)
        return sum(
            1
            for line in res.stdout.splitlines()
            if line.startswith("-") and not line.startswith("---")
        )

    def reset(self) -> str:
        """Restores worktree back to clean HEAD, preserving build target caches."""
        self._run_git("checkout", "--force", "HEAD")
        self._run_git(
            "clean", "-fd", "-e", "target", "-e", CARGO_TARGET_CACHE_SUBDIR, "-e", ".mjolnir_tags"
        )
        return "Sandbox reset to clean baseline."

    def _build_env(self) -> dict[str, str]:
        """Builds sanitized environment whitelisting build toolchains while scrubbing secrets."""
        env = {
            k: v
            for k, v in os.environ.items()
            if k in SANDBOX_ALLOWED_ENV_VARS or k.startswith(("CARGO_", "RUST_"))
        }
        env.setdefault("RUSTUP_AUTO_INSTALL", "0")
        if "CARGO_TARGET_DIR" not in env:
            src_target = self.source_code_dir / "target"
            if src_target.is_dir() and os.access(src_target, os.W_OK):
                env["CARGO_TARGET_DIR"] = str(src_target)
            else:
                cache_target = self.workspace_dir / CARGO_TARGET_CACHE_SUBDIR
                cache_target.mkdir(parents=True, exist_ok=True)
                env["CARGO_TARGET_DIR"] = str(cache_target)
        return env

    async def run_harness_command_async(
        self, command: str, timeout_seconds: int = HARNESS_COMMAND_TIMEOUT_SECONDS
    ) -> CommandRecord:
        """Executes a test harness command inside the isolated sandbox and records its output."""
        effective_timeout = max(5, min(timeout_seconds, HARNESS_COMMAND_TIMEOUT_SECONDS))
        env = self._build_env()

        res = await asyncio.to_thread(
            run_command_capture,
            ["bash", "-c", command],
            cwd=str(self.worktree_dir),
            timeout=effective_timeout,
            env=env,
        )

        combined = res.stdout or ""
        if res.stderr:
            combined = (
                combined + "\n" if combined and not combined.endswith("\n") else combined
            ) + res.stderr

        record = CommandRecord(
            command=command,
            returncode=res.returncode,
            output=combined.strip() or "(no output)",
        )
        self.command_history.append(record)
        return record
