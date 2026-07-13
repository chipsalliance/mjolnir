# Agent Tools

Python-based tools which can be used by agents to analyze code.

## Files

- **`ast_search.py`**: Uses tree-sitter (via ast-grep / sg) to perform structural syntax searches across code.
- **`ctags_search.py`**: Finds definitions of symbols (functions, structs, macros, variables) across the codebase using Universal Ctags.
- **`glob.py`**: Discovers files matching specific patterns or extensions in the workspace.
- **`grep_search.py`**: Executes fast regex keyword searches inside files using ripgrep.
- **`read_file.py`**: Allows agents to safely view source file contents.
