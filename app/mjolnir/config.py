# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Central configuration data structures for Mjolnir."""

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class AppConfig:
    """Immutable application configuration instantiated once at application startup."""

    code_dir: Path = field(default_factory=lambda: Path(".").absolute())
    workspace_dir: Optional[Path] = None
    output_dir: Optional[Path] = None
    run_id: Optional[str] = None
    gemini_api_key: Optional[str] = field(default_factory=lambda: os.environ.get("GEMINI_API_KEY"))
    google_cloud_project: Optional[str] = field(
        default_factory=lambda: os.environ.get("GOOGLE_CLOUD_PROJECT")
    )
    google_cloud_location: Optional[str] = field(
        default_factory=lambda: os.environ.get("GOOGLE_CLOUD_LOCATION")
    )

    @classmethod
    def from_env(
        cls,
        code_dir: Optional[str] = None,
        workspace_dir: Optional[str] = None,
        output_dir: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> "AppConfig":
        """Instantiates AppConfig with explicit parameters or default working directory."""
        target_code_dir = Path(code_dir).absolute() if code_dir else Path(".").absolute()
        target_workspace_dir = Path(workspace_dir).absolute() if workspace_dir else None
        target_output_dir = Path(output_dir).absolute() if output_dir else None

        return cls(
            code_dir=target_code_dir,
            workspace_dir=target_workspace_dir,
            output_dir=target_output_dir,
            run_id=run_id,
        )
