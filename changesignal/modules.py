"""Module map loading and rule-based owner detection.  Owner: wonlin91 (detect).

Walking-skeleton version: folder-prefix and exact-path matching only.
TODO (detect): glob patterns, validation of modules.yml (missing owner, overlapping paths),
reading the map from the base branch so a PR cannot edit its own owners away.
"""
import yaml


def load_modules(path=".changesignal/modules.yml"):
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("modules", [])


def _matches(file, pattern):
    if pattern.endswith("/"):
        return file.startswith(pattern)
    return file == pattern


def find_affected(changed_files, modules, author):
    """Return modules owned by someone other than `author` whose paths the PR touches.

    -> [{"module": str, "owner": str, "kind": "owned_path", "files": [str]}]
    """
    author = author.lower()
    affected = []
    for module in modules:
        owner = module["owner"]
        if owner.lower() == author:
            continue
        files = [f for f in changed_files
                 if any(_matches(f, p) for p in module.get("paths", []))]
        if files:
            affected.append({"module": module["name"], "owner": owner,
                             "kind": "owned_path", "files": files})
    return affected
