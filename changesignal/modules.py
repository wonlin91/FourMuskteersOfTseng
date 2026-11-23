"""Module map loading and rule-based owner detection.  Owner: wonlin91 (detect).

Paths are folder prefixes ("dir/"), exact files, or globs (`*`, `?`, `**`).
parse_modules rejects a malformed map with a short ModuleMapError that names the module and the fix
(the message ends up in a 140-character commit status).
"""
import difflib
import functools
import re

import yaml


class ModuleMapError(ValueError):
    """The module map is missing or malformed. ChangeSignal must not pass a PR on a broken map."""


ALLOWED_KEYS = ("name", "owner", "paths", "interfaces")
# GitHub login: letters, digits and single "-", not starting or ending with "-", at most 39 chars.
_OWNER_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?")


def _label(m, i):
    """How an error names a module: its name if it has a usable one, else its position."""
    name = m.get("name") if isinstance(m, dict) else None
    return f'module "{name}"' if isinstance(name, str) and name else f"module #{i}"


def _check_path(label, p):
    """A path that can never match anything is a silent hole in the map, so reject it."""
    if not isinstance(p, str) or not p.strip():
        raise ModuleMapError(f"{label}: paths must be non-empty strings")
    if p != p.strip():
        raise ModuleMapError(f'{label}: path "{p}" has spaces around it')
    if p.startswith("./") or p.startswith("/"):
        raise ModuleMapError(f'{label}: path "{p}" must be relative to the repo root (no leading "./" or "/")')
    if "\\" in p:
        raise ModuleMapError(f'{label}: path "{p}" must use "/" not "\\"')


def parse_modules(text):
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ModuleMapError(f"not valid YAML ({e.__class__.__name__})") from e
    modules = data.get("modules") if isinstance(data, dict) else None
    if not isinstance(modules, list) or not modules:
        raise ModuleMapError("needs a non-empty top-level 'modules' list")

    names = {}       # name -> position, to catch duplicate names
    path_owner = {}  # path -> module name, to catch a path claimed twice
    for i, m in enumerate(modules, 1):
        label = _label(m, i)
        if not isinstance(m, dict):
            raise ModuleMapError(f"{label} must be a mapping with name, owner and paths")
        for key in m:
            if key not in ALLOWED_KEYS:
                hint = difflib.get_close_matches(str(key), ALLOWED_KEYS, n=1)
                tip = f' (did you mean "{hint[0]}"?)' if hint else f" (allowed: {', '.join(ALLOWED_KEYS)})"
                raise ModuleMapError(f'{label}: unknown key "{key}"{tip}')
        for key in ("name", "owner"):
            if not isinstance(m.get(key), str) or not m[key].strip():
                raise ModuleMapError(f'{label}: missing "{key}" (a non-empty string)')
        if not isinstance(m.get("paths"), list) or not m["paths"]:
            raise ModuleMapError(f'{label}: "paths" must be a non-empty list')

        if m["name"] in names:
            raise ModuleMapError(f'{label}: name already used by module #{names[m["name"]]}; names must be unique')
        names[m["name"]] = i

        if not _OWNER_RE.fullmatch(m["owner"]):
            shown = m["owner"] if len(m["owner"]) <= 12 else m["owner"][:12] + "..."
            raise ModuleMapError(f'{label}: owner "{shown}" is not a GitHub username '
                                 "(a-z 0-9 -, max 39, no @ or spaces)")

        for p in m["paths"]:
            _check_path(label, p)
            if p in path_owner and path_owner[p] != m["name"]:
                raise ModuleMapError(f'{label}: path "{p}" is already owned by module "{path_owner[p]}"')
            path_owner.setdefault(p, m["name"])
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


def _reject_folders_without_slash(changed_files, modules):
    """Fail closed on a folder written without its trailing "/" (e.g. "changesignal").

    Text alone cannot tell it from a file like "Makefile", but the PR's file list can: if a changed
    file lives under "<path>/", then <path> is a folder and would otherwise silently match nothing,
    so its owner would never be asked.
    """
    for module in modules:
        for p in module.get("paths", []):
            if p.endswith("/") or "*" in p or "?" in p:
                continue
            if any(f.startswith(p + "/") for f in changed_files):
                raise ModuleMapError(f'module "{module["name"]}": path "{p}" is a folder; write "{p}/"')


def find_affected(changed_files, modules, author):
    """Return modules owned by someone other than `author` whose paths the PR touches.

    -> [{"module": str, "owner": str, "kind": "owned_path", "files": [str]}]
    """
    _reject_folders_without_slash(changed_files, modules)
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
