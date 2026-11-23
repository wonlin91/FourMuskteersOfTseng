"""Cross-module caller detection.  Owner: wonlin91 (detect).

Answers "I know which function I changed, but who else calls it?" for Python code.

Approach (static, stdlib only):
1. For each changed .py file that still exists, read the PR patch and collect the new-side
   line numbers it touches (added lines, plus the lines around a deletion).
2. Parse the file with `ast`. A top-level function, class or method (reported as
   `Class.method`) is "changed" when its line span (decorators included) contains a touched
   line. A class counts as changed when lines outside its methods change, or its __init__.
   No patch for a file (binary / too large / not given) -> every symbol in it counts.
3. Turn the file path into its import name (`pipeline/preprocess.py` -> `pipeline.preprocess`,
   `pkg/__init__.py` -> `pkg`).
4. Parse every other .py file that belongs to a module in modules.yml. Read its imports
   (absolute, `as` aliases, `from pkg import module`, relative `from .x import y`) to learn
   which local names point at a changed module or at a symbol inside it, then look at every
   call: `name(...)`, `alias.name(...)`, `a.b.name(...)`, `Class.method(...)`. If the class
   was imported by name, any `something.method(...)` is also reported (we cannot know the
   type of `something`, so this is a guess).
5. Report one entry per (caller file, symbol) for callers in a *different* module than the
   changed file, with the first call line and the source of the enclosing function.

Known limits (results are "possible" callers, not proof, and some callers are missed):
- Dynamic calls are invisible: getattr(), importlib, calls through variables or callbacks
  (`f = crop_regions; f(x)`), dependency injection, re-exports through another
  package's __init__, and anything after the name is shadowed or reassigned.
- Method calls are matched by name only, so `obj.run()` may be a different class's `run`.
- Import names come from the path relative to the repo root (no `src/` layouts, no
  sys.path tricks). Deleted functions are not seen (they are not in the new file).
- Only Python is analysed: callers in other languages, configs, notebooks or templates
  are not found, and files that fail to parse are skipped.
"""
import ast
import os
import re
from pathlib import Path

from .modules import _matches

SKIP_DIRS = {".git", "venv", ".venv", "node_modules", "__pycache__"}
FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)
_HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def find_callers(changed_files, modules, repo_root=".", patches=None, max_snippet_lines=30):
    """patches: {path: unified-diff patch text from GitHub's PR files API (hunk headers '@@ -a,b +c,d @@')}.
    -> [{"module", "owner", "kind": "possible_caller", "symbol", "location": "path:line",
         "files": [path], "snippet": "<source of the calling function or surrounding lines>",
         "changed_file": "<the changed file that defines symbol>"}]
    """
    root = Path(repo_root)
    targets = _changed_targets(changed_files, modules, root, patches or {})
    if not targets:
        return []

    found = []  # (caller path, line, symbol, module, target, source lines, tree)
    for path in _python_files(root):
        module = _module_of(path, modules)
        if module is None:
            continue
        source, tree = _parse(root / path)
        if tree is None:
            continue
        first_call = {}  # (target, symbol) -> first line it is called on
        for target, symbol, line in _calls_to_targets(tree, path, targets):
            if targets[target]["module"] == module["name"]:
                continue  # same module: its owner is already involved
            key = (target, symbol)
            first_call[key] = min(line, first_call.get(key, line))
        for (target, symbol), line in first_call.items():
            found.append((path, line, symbol, module, target, source.splitlines(), tree))

    found.sort(key=lambda f: f[:3])
    return [{"module": module["name"], "owner": module["owner"], "kind": "possible_caller",
             "symbol": symbol, "location": f"{path}:{line}", "files": [path],
             "changed_file": targets[target]["path"],
             "snippet": _snippet(lines, tree, line, max_snippet_lines)}
            for path, line, symbol, module, target, lines, tree in found]


# --- what changed -----------------------------------------------------------------
def _changed_targets(changed_files, modules, root, patches):
    """{import name: {"path", "module": module name or None, "symbols": {changed symbol}}}"""
    targets = {}
    for path in changed_files:
        if not path.endswith(".py"):
            continue
        _, tree = _parse(root / path)
        if tree is None:  # deleted in this PR, unreadable, or not valid Python
            continue
        patch = patches.get(path)
        touched = None if patch is None else _touched_lines(patch)
        symbols = _changed_symbols(tree, touched)
        if symbols:
            module = _module_of(path, modules)
            targets[_import_name(path)] = {"path": path, "symbols": symbols,
                                           "module": module["name"] if module else None}
    return targets


def _touched_lines(patch):
    """New-file line numbers an edit touches: added lines, and both sides of a deletion."""
    touched = set()
    line = None  # number of the next line on the new side
    for text in patch.splitlines():
        header = _HUNK_HEADER.match(text)
        if header:
            start, count = int(header.group(1)), header.group(2)
            # In a pure-deletion hunk (+c,0) git names the line *before* the gap.
            line = start + 1 if count == "0" else start
        elif line is None or text.startswith("\\"):  # before first hunk / "\ No newline"
            continue
        elif text.startswith("+"):
            touched.add(line)
            line += 1
        elif text.startswith("-"):
            touched.update((line - 1, line))
        else:  # context line
            line += 1
    return touched


def _changed_symbols(tree, touched):
    """Names of top-level functions/classes and `Class.method`s whose lines were touched.
    touched=None means "unknown": everything counts as changed."""
    def hit(lines):
        return touched is None or not touched.isdisjoint(lines)

    symbols = set()
    for node in tree.body:
        if isinstance(node, FUNCTION_NODES) and hit(_span(node)):
            symbols.add(node.name)
        elif isinstance(node, ast.ClassDef):
            methods = [n for n in node.body if isinstance(n, FUNCTION_NODES)]
            changed = [m.name for m in methods if hit(_span(m))]
            symbols.update(f"{node.name}.{name}" for name in changed)
            outside_methods = set(_span(node)).difference(*(_span(m) for m in methods))
            if hit(outside_methods) or "__init__" in changed:
                symbols.add(node.name)
    return symbols


def _span(node):
    first = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
    return range(first, node.end_lineno + 1)


# --- who calls it -------------------------------------------------------------------
def _calls_to_targets(tree, path, targets):
    """Yield (target import name, symbol, line) for each call in `tree` to a changed symbol."""
    module_aliases, names = _imports_of(tree, path, targets)
    if not module_aliases and not names:
        return
    # Methods of classes imported by name: `x.method(...)` may be one of them.
    methods = {}
    for target, name in names.values():
        for symbol in targets[target]["symbols"]:
            if symbol.startswith(name + "."):
                methods.setdefault(symbol.split(".", 1)[1], []).append((target, symbol))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        hit = _resolve(_dotted(node.func), module_aliases, names, targets)
        if hit:
            yield hit[0], hit[1], node.lineno
        elif isinstance(node.func, ast.Attribute):
            for target, symbol in methods.get(node.func.attr, []):
                yield target, symbol, node.lineno


def _imports_of(tree, path, targets):
    """Local names that refer to changed modules or to names inside them.

    -> (module_aliases {local dotted name: target}, names {local name: (target, name)})
    """
    module_aliases, names = {}, {}
    package = _package_of(path)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for target in targets:
                    if alias.asname and alias.name == target:  # import a.b as x
                        module_aliases[alias.asname] = target
                    elif not alias.asname and (alias.name == target
                                               or alias.name.startswith(target + ".")):
                        module_aliases[target] = target  # import a.b -> used as a.b.f()
        elif isinstance(node, ast.ImportFrom):
            source = _absolute_module(node.module, node.level, package)
            if source is None:
                continue
            for alias in node.names:
                local = alias.asname or alias.name
                if f"{source}.{alias.name}" in targets:  # from a import b (b is the module)
                    module_aliases[local] = f"{source}.{alias.name}"
                elif source in targets and alias.name == "*":
                    for symbol in targets[source]["symbols"]:
                        top = symbol.split(".")[0]
                        names[top] = (source, top)
                elif source in targets:  # from a.b import f [as g]
                    names[local] = (source, alias.name)
    return module_aliases, names


def _resolve(dotted, module_aliases, names, targets):
    """Map a callee like `crop`, `pp.crop_regions` or `Cropper.run` to (target, symbol)."""
    if not dotted:
        return None
    first, _, rest = dotted.partition(".")
    if first in names:
        target, name = names[first]
        symbol = f"{name}.{rest}" if rest else name
    else:
        prefix = next((p for p in sorted(module_aliases, key=len, reverse=True)
                       if dotted.startswith(p + ".")), None)
        if prefix is None:
            return None
        target, symbol = module_aliases[prefix], dotted[len(prefix) + 1:]
    return (target, symbol) if symbol in targets[target]["symbols"] else None


def _dotted(node):
    """`a.b.c` for a Name/Attribute chain, else None (e.g. `f()()` or `x[0].g`)."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr}" if base else None
    return None


# --- paths, files, snippets -----------------------------------------------------------
def _import_name(path):
    parts = path[:-len(".py")].split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _package_of(path):
    """The package a relative import in `path` starts from."""
    name = _import_name(path)
    return name if path.endswith("__init__.py") else name.rpartition(".")[0]


def _absolute_module(module, level, package):
    """Resolve `from ..x import y` (level=2, module='x') against the importing package."""
    if level == 0:
        return module
    parts = package.split(".") if package else []
    if level - 1 > len(parts):
        return None  # goes above the repo root
    base = parts[:len(parts) - (level - 1)]
    return ".".join(base + ([module] if module else [])) or None


def _module_of(path, modules):
    return next((m for m in modules if any(_matches(path, p) for p in m.get("paths", []))), None)


def _python_files(root):
    """Repo-relative POSIX paths of all .py files, in a stable order."""
    for folder, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(files):
            if name.endswith(".py"):
                yield (Path(folder) / name).relative_to(root).as_posix()


def _parse(file):
    """(source, ast) or (None, None) when the file is missing, unreadable or not valid Python."""
    try:
        source = file.read_text(encoding="utf-8-sig")
        return source, ast.parse(source, filename=str(file))
    except (OSError, ValueError, SyntaxError, RecursionError):  # ValueError: bad encoding
        return None, None


def _snippet(lines, tree, line, max_lines):
    """Source of the innermost function around `line`, or +-5 lines at module level."""
    around = [n for n in ast.walk(tree)
              if isinstance(n, FUNCTION_NODES) and n.lineno <= line <= n.end_lineno]
    if around:
        inner = max(around, key=lambda n: n.lineno)
        start, end = inner.lineno, inner.end_lineno
    else:
        start, end = max(1, line - 5), min(len(lines), line + 5)
    if end - start + 1 > max_lines:  # too long: keep a window that contains the call
        start = max(start, min(line - max_lines // 2, end - max_lines + 1))
        end = start + max_lines - 1
    return "\n".join(lines[start - 1:end])
