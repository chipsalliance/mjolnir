# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
from typing import Callable

TOOL_PROMPT_GUIDANCE: dict[str, str] = {
    "ctags_search": (
        "**`ctags_search` (O(1) Symbol Definitions):** Prefer FIRST whenever you need to jump "
        "directly to the definition `<file>:<line>` of a function, struct, typedef, enum, macro, "
        "or global variable via the pre-built `.git/tags` index."
    ),
    "ast_search": (
        "**`ast_search` (Structural AST Search):** Use `ast-grep` patterns (`$VAR` for single AST "
        "nodes, `$$$ARGS` for variadic arguments) with `lang` (`c`, `rust`, `verilog`) to match "
        "structural code patterns, call shapes, or hardening idioms."
    ),
    "grep_search": (
        "**`grep_search` (Regex / Call-Site Search):** Use `ripgrep` to trace callers, "
        "cross-references, register names, or string literals across files when looking for "
        "usages rather than symbol definitions."
    ),
    "glob": (
        "**`glob` (File Path Discovery):** Use glob patterns (e.g., `*manifest*.h`, `**/epmp*.c`) "
        "to locate related header files, drivers, or module layouts by filename without scanning "
        "file contents."
    ),
    "read_file": (
        "**`read_file` (Scoped Line-Range Reading):** After locating a target `<file>:<line>` via "
        "`ctags_search`, `ast_search`, or `grep_search`, read focused `start_line` and `end_line` "
        "bounds instead of reading entire large files."
    ),
    "ask_project_expert": (
        "**`ask_project_expert` (Architectural & Threat Model Consultation):** Consult the Project "
        "Expert when you need clarification on project-level architectural conventions, "
        "cross-subsystem trust boundaries, hardware/ePMP/OTP guarantees, or whether an omitted "
        "check is intentionally enforced by hardware or an earlier boot stage."
    ),
}


def format_tool_guidance(tools: list[Callable]) -> str:
    """Renders Markdown bullet guidance strictly for the tools present in the provided tool list."""
    lines = []
    for tool_fn in tools:
        tool_name = getattr(tool_fn, "__name__", str(tool_fn))
        guidance = TOOL_PROMPT_GUIDANCE.get(tool_name)
        if guidance:
            lines.append(f"- {guidance}")
    return "\n".join(lines)
