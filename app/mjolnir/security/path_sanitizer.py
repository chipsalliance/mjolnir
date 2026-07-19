# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Workspace path sanitization and boundary safety validation using modern Python 3.12+ types."""

from pathlib import Path


def resolve_workspace_path(
    user_path: str | Path,
    base_dir: str | Path | None = None,
) -> tuple[Path | None, str | None]:
    """Resolves user_path relative to base_dir and validates path traversal boundaries.

    Args:
        user_path: Target path requested by a tool.
        base_dir: Root workspace directory. Defaults to current working directory.

    Returns:
        tuple[Path | None, str | None]: (resolved_path, None) if safe, or (None, error_msg) if unsafe.
    """
    root = Path(base_dir or ".").resolve()

    try:
        target = (root / user_path).resolve()
    except Exception as e:
        return None, f"Error resolving path '{user_path}': {str(e)}"

    if not target.is_relative_to(root):
        return None, f"Error: Access denied. Path traversal detected for '{user_path}'."

    return target, None
