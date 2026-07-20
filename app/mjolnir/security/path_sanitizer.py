# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Workspace path sanitization and boundary safety validation using modern Python 3.12+ types."""

from pathlib import Path


def resolve_workspace_path(
    user_path: str | Path,
    base_dir: str | Path | None = None,
) -> Path:
    """Resolves user_path relative to base_dir and validates path traversal boundaries.

    Args:
        user_path: Target path requested by a tool.
        base_dir: Root workspace directory. Defaults to current working directory.

    Returns:
        Path: Resolved absolute path.

    Raises:
        ValueError: If path resolution fails or path traversal outside base_dir is detected.
    """
    root = Path(base_dir or ".").resolve()

    try:
        target = (root / user_path).resolve()
    except Exception as e:
        raise ValueError(f"Error resolving path '{user_path}': {e}") from e

    if not target.is_relative_to(root):
        raise ValueError(f"Access denied. Path traversal detected for '{user_path}'.")

    return target
