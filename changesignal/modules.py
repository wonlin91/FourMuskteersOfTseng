"""Module map loading and rule-based owner detection.  Owner: wonlin91 (detect).

Walking-skeleton version: folder-prefix and exact-path matching only.
TODO (detect): glob patterns, validation of modules.yml (missing owner, overlapping paths),
clearer errors for a malformed map.
"""
import yaml


class ModuleMapError(ValueError):
    """The module map is missing or malformed. ChangeSignal must not pass a PR on a broken map."""


def parse_modules(text):
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ModuleMapError(f"not valid YAML ({e.__class__.__name__})") from e
    modules = data.get("modules") if isinstance(data, dict) else None
    if not isinstance(modules, list) or not modules:
        raise ModuleMapError("needs a non-empty top-level 'modules' list")
    for i, m in enumerate(modules, 1):
        ok = (isinstance(m, dict) and isinstance(m.get("name"), str) and isinstance(m.get("owner"), str)
              and isinstance(m.get("paths"), list) and m["paths"]
              and all(isinstance(p, str) and p for p in m["paths"]))
        if not ok:
            raise ModuleMapError(f"module #{i} needs 'name', 'owner' and a non-empty 'paths' list")
    return modules


def load_modules(path=".changesignal/modules.yml"):
    with open(path, encoding="utf-8") as f:
        return parse_modules(f.read())


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
