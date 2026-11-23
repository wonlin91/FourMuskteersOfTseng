"""Cross-module caller detection.  Owner: wonlin91 (detect).

STUB for the walking skeleton: always returns no callers.
TODO (detect): parse changed Python files with `ast`, collect changed function names,
then scan other modules for calls to them.
"""


def find_callers(changed_files, modules, repo_root="."):
    """-> [{"module", "owner", "kind": "possible_caller", "symbol", "location": "path:line"}]"""
    return []
