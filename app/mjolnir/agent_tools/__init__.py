# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
from typing import Callable

from constants import TOOL_PROMPT_GUIDANCE


def format_tool_guidance(tools: list[Callable]) -> str:
    """Renders Markdown bullet guidance strictly for the tools present in the provided tool list."""
    lines = []
    for tool_fn in tools:
        tool_name = getattr(tool_fn, "__name__", str(tool_fn))
        guidance = TOOL_PROMPT_GUIDANCE.get(tool_name)
        if guidance:
            lines.append(f"- {guidance}")
    return "\n".join(lines)
