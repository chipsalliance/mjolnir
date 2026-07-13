# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import os
import fnmatch
import subprocess
from utilities.agent_context import CURRENT_RUN_ID
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
        dir_path: The path to the directory or file to search within. Defaults to ".".
        case_sensitive: Whether the search should be case-sensitive. Defaults to False.
        respect_git_ignore: Whether to respect .gitignore patterns. Defaults to True.
        respect_gemini_ignore: Whether to respect .geminiignore patterns. Defaults to True (currently stubbed).
    """
    code_dir = os.environ.get("CODE_DIR", ".")
    search_path = os.path.abspath(os.path.join(code_dir, dir_path))
    if not search_path.startswith(os.path.abspath(code_dir)):
        return "Error: Access denied. Path traversal detected."

    if not os.path.exists(search_path):
        return f"Error: Path '{dir_path}' does not exist."

    run_id = CURRENT_RUN_ID.get()
    prefix = f"[{run_id}] " if run_id else ""
    print(
        f"{prefix}[Tool Execution] glob: pattern='{pattern}', dir_path='{dir_path}', "
        f"case_sensitive={case_sensitive}, respect_git_ignore={respect_git_ignore}",
        flush=True,
    )

    try:
        files = []
        use_fallback = True

        if os.path.isfile(search_path):
            cwd_path = os.path.dirname(search_path)
            target_name = os.path.basename(search_path)
            if respect_git_ignore:
                try:
                    res = subprocess.run(
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
                        capture_output=True,
                        text=True,
                        check=True,
                        timeout=5.0,
                    )
                    if res.stdout.strip():
                        files = [target_name]
                    else:
                        files = []
                    use_fallback = False
                except (
                    subprocess.CalledProcessError,
                    subprocess.TimeoutExpired,
                    FileNotFoundError,
                    OSError,
                ):
                    use_fallback = True
            if use_fallback:
                files = [target_name]
        else:
            if respect_git_ignore:
                try:
                    res = subprocess.run(
                        ["git", "ls-files", "-c", "-o", "--exclude-standard"],
                        cwd=search_path,
                        capture_output=True,
                        text=True,
                        check=True,
                        timeout=5.0,
                    )
                    files = res.stdout.splitlines()
                    use_fallback = False
                except (
                    subprocess.CalledProcessError,
                    subprocess.TimeoutExpired,
                    FileNotFoundError,
                    OSError,
                ):
                    use_fallback = True

            if use_fallback:
                for root, _, filenames in os.walk(search_path):
                    for filename in filenames:
                        full_path = os.path.join(root, filename)
                        rel_path = os.path.relpath(full_path, search_path)
                        files.append(rel_path)

        matches = []
        for f in files:
            if os.path.isfile(search_path):
                rel_to_code = os.path.relpath(search_path, os.path.abspath(code_dir))
                candidates = [f, rel_to_code, search_path]
            else:
                candidates = [f]

            for cand in candidates:
                if case_sensitive:
                    if fnmatch.fnmatchcase(cand, pattern):
                        matches.append(f)
                        break
                else:
                    if fnmatch.fnmatchcase(cand.lower(), pattern.lower()):
                        matches.append(f)
                        break

        if not matches:
            return f"No files matching '{pattern}' found within '{dir_path}'."

        # Convert to absolute paths as per Gemini CLI spec
        if os.path.isfile(search_path):
            absolute_matches = [search_path]
        else:
            absolute_matches = [
                os.path.abspath(os.path.join(search_path, m)) for m in matches
            ]

        display_matches = absolute_matches[:500]
        result = (
            f"Found {len(absolute_matches)} file(s) matching '{pattern}' within '{dir_path}':\n"
            + "\n".join(display_matches)
        )
        if len(absolute_matches) > 500:
            result += f"\n\n... [Warning: Only first 500 matches shown out of {len(absolute_matches)} total]"
        return result
    except Exception as e:
        return f"Error executing glob: {str(e)}"
