# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import os
import fnmatch
import subprocess
from utilities.decorators import limit_tool_output


@limit_tool_output(max_chars=40000)
def glob(
    pattern: str,
    dir_path: str = ".",
    case_sensitive: bool = False,
    respect_git_ignore: bool = True,
    respect_gemini_ignore: bool = True,
) -> str:
    """Finds files matching specific glob patterns across the workspace.

    Args:
        pattern: The glob pattern to match against (e.g., "*.py", "src/**/*.js").
        dir_path: The path to the directory to search within. Defaults to ".".
        case_sensitive: Whether the search should be case-sensitive. Defaults to False.
        respect_git_ignore: Whether to respect .gitignore patterns. Defaults to True.
        respect_gemini_ignore: Whether to respect .geminiignore patterns. Defaults to True (currently stubbed).
    """
    code_dir = os.environ.get("CODE_DIR", ".")
    search_path = os.path.abspath(os.path.join(code_dir, dir_path))
    if not search_path.startswith(os.path.abspath(code_dir)):
        return "Error: Access denied. Path traversal detected."

    print(
        f" [Tool Execution] glob: pattern='{pattern}', dir_path='{dir_path}', "
        f"case_sensitive={case_sensitive}, respect_git_ignore={respect_git_ignore}",
        flush=True,
    )

    files = []
    use_fallback = True

    if respect_git_ignore:
        try:
            res = subprocess.run(
                ["git", "ls-files", "-c", "-o", "--exclude-standard"],
                cwd=search_path,
                capture_output=True,
                text=True,
                check=True,
            )
            files = res.stdout.splitlines()
            use_fallback = False
        except (subprocess.CalledProcessError, FileNotFoundError):
            use_fallback = True

    if use_fallback:
        for root, _, filenames in os.walk(search_path):
            for filename in filenames:
                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, search_path)
                files.append(rel_path)

    matches = []
    for f in files:
        if case_sensitive:
            if fnmatch.fnmatchcase(f, pattern):
                matches.append(f)
        else:
            if fnmatch.fnmatchcase(f.lower(), pattern.lower()):
                matches.append(f)

    if not matches:
        return f"No files matching '{pattern}' found within '{dir_path}'."

    # Convert to absolute paths as per Gemini CLI spec
    absolute_matches = [os.path.abspath(os.path.join(search_path, m)) for m in matches]

    display_matches = absolute_matches[:500]
    result = (
        f"Found {len(absolute_matches)} file(s) matching '{pattern}' within '{dir_path}':\n"
        + "\n".join(display_matches)
    )
    if len(absolute_matches) > 500:
        result += f"\n\n... [Warning: Only first 500 matches shown out of {len(absolute_matches)} total]"
    return result
