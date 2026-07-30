# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Centralized prompt registry and loader for ADK agents."""

import asyncio
from pathlib import Path


class PromptRegistry:
    """Discovers and loads prompt template assets from centralized locations."""

    def __init__(self, base_dir: Path | str | None = None) -> None:
        if base_dir:
            self.prompts_dir = Path(base_dir).resolve()
        else:
            self.prompts_dir = (
                Path(__file__).resolve().parent.parent / "providers" / "adk" / "prompts"
            )

    def load_prompt(self, prompt_name: str, fallback: str = "") -> str:
        """Loads prompt template markdown file by name (e.g., 'ingestion', 'auditor')."""
        filename = prompt_name if prompt_name.endswith(".md") else f"{prompt_name}.md"
        prompt_path = self.prompts_dir / filename

        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8").strip()

        return fallback

    async def load_prompt_async(self, prompt_name: str, fallback: str = "") -> str:
        """Loads prompt template markdown file asynchronously by name."""
        return await asyncio.to_thread(self.load_prompt, prompt_name, fallback=fallback)


prompt_registry = PromptRegistry()
