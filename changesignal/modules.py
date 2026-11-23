"""Module map loading and rule-based owner detection.  Owner: wonlin91 (detect).

Paths are folder prefixes ("dir/"), exact files, or globs (`*`, `?`, `**`).
TODO (detect): stricter validation of modules.yml (duplicate names, owner format, overlapping paths),
clearer errors for a malformed map.
"""
import functools
import re

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


@functools.lru_cache(maxsize=256)
def _glob_to_regex(pattern):
    """Translate a path glob to a compiled regex.

    `*` and `?` stay inside one path segment (never cross "/"), unlike fnmatch.
    `**/` matches zero or more whole folders; a `**` anywhere else matches anything.
    Written by hand because glob.translate / PurePath.full_match need Python 3.13 (CI runs 3.11).
    """
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out))



def _matches(file, pattern):
    """Does `file` fall under `pattern`? (folder prefix "dir/", exact path, or a glob)"""
    if "*" in pattern or "?" in pattern:
        return _glob_to_regex(pattern).fullmatch(file) is not None
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
