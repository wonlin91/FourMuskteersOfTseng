import pytest

from changesignal.modules import ModuleMapError, _matches, find_affected, load_modules, parse_modules


@pytest.mark.parametrize("file, pattern, expected", [
    # * stays inside one folder
    ("practice/a.py", "practice/*.py", True),
    ("practice/sub/a.py", "practice/*.py", False),
    ("README.md", "*.md", True),
    ("docs/a.md", "*.md", False),
    # ** crosses folders, including zero folders
    ("practice/a.py", "practice/**/*.py", True),
    ("practice/x/y/a.py", "practice/**/*.py", True),
    ("README.md", "**/README.md", True),
    ("docs/README.md", "**/README.md", True),
    ("docs/deep/README.md", "**/README.md", True),
    ("docs/README.txt", "**/README.md", False),
    ("practice/x/y/a.py", "practice/**", True),
    # ? is exactly one character, not "/"
    ("practice/a.py", "practice/?.py", True),
    ("practice/ab.py", "practice/?.py", False),
    ("practice/.py", "practice/?.py", False),
    # old behaviour is unchanged
    ("practice/a.py", "practice/", True),
    ("practice/x/a.py", "practice/", True),
    ("other/a.py", "practice/", False),
    ("changesignal/card.py", "changesignal/card.py", True),
    ("changesignal/card.pyc", "changesignal/card.py", False),
    # regex special characters are literal
    ("a.py", "a.py", True),
    ("aXpy", "a.py", False),
    ("aXpy", "a*.py", False),
    ("a+b.py", "a+b*.py", True),
    ("aab.py", "a+b*.py", False),
    ("x(1).py", "x(1).py", True),
    ("x(1).py", "x(?).py", True),
    # a glob must match the whole path, not just a part of it
    ("src/a.py.bak", "*.py", False),
    ("src/a.py", "a.py*", False),
])
def test_matches(file, pattern, expected):
    assert _matches(file, pattern) is expected


def test_glob_in_find_affected():
    modules = [
        {"name": "docs", "owner": "alice", "paths": ["**/README.md"]},
        {"name": "code", "owner": "bob", "paths": ["pkg/*.py"]},
    ]
    result = find_affected(["README.md", "pkg/a.py", "pkg/sub/b.py"], modules, "carol")
    assert {(a["module"], tuple(a["files"])) for a in result} == {
        ("docs", ("README.md",)), ("code", ("pkg/a.py",))}


def test_repo_modules_yml_still_loads():
    assert load_modules(".changesignal/modules.yml")


# ---- parse_modules validation (issue #6) ----

def _map(*modules):
    """Build modules.yml text from (name, owner, paths) tuples; paths are YAML flow items."""
    out = ["modules:"]
    for name, owner, paths in modules:
        out += [f"  - name: {name}", f"    owner: {owner}", f"    paths: [{paths}]"]
    return "\n".join(out) + "\n"


def _error(text):
    with pytest.raises(ModuleMapError) as exc:
        parse_modules(text)
    msg = str(exc.value)
    assert len(msg) <= 100, f"too long for the 140-char status ({len(msg)}): {msg}"
    return msg


def test_valid_map_passes():
    assert len(parse_modules(_map(("a", "alice", '"x/"'), ("b", "bob-1", '"y/*.py", "z.md"')))) == 2


def test_unknown_key_suggests_paths():
    msg = _error("modules:\n  - name: card\n    owner: alice\n    path: [x/]\n")
    assert 'module "card"' in msg and '"path"' in msg and 'did you mean "paths"' in msg


def test_unknown_key_without_close_match_lists_allowed_keys():
    msg = _error("modules:\n  - name: card\n    owner: alice\n    paths: [x/]\n    color: red\n")
    assert 'module "card"' in msg and '"color"' in msg and "paths" in msg


def test_typo_in_owner_key_is_caught():
    msg = _error("modules:\n  - name: card\n    owners: alice\n    paths: [x/]\n")
    assert 'module "card"' in msg and 'did you mean "owner"' in msg


def test_duplicate_name_is_rejected():
    msg = _error(_map(("card", "alice", '"x/"'), ("card", "bob", '"y/"')))
    assert 'module "card"' in msg and "unique" in msg


@pytest.mark.parametrize("owner", [
    '"@wonlin91"', '"won lin"', '"李秉倫"', '"-alice"', '"alice-"', '"a_b"', "a" * 40, '"alice "',
])
def test_bad_owner_is_rejected(owner):
    msg = _error(_map(("card", owner, '"x/"')))
    assert 'module "card"' in msg and "GitHub username" in msg


@pytest.mark.parametrize("owner", ["a", "a" * 39, "Ab-1", "a--b"])
def test_good_owner_is_accepted(owner):
    parse_modules(_map(("card", owner, '"x/"')))


def test_same_path_in_two_modules_is_rejected():
    msg = _error(_map(("a", "alice", '"x/", "shared.py"'), ("b", "bob", '"shared.py"')))
    assert 'module "b"' in msg and '"shared.py"' in msg and '"a"' in msg


@pytest.mark.parametrize("path", ['"./x.py"', '"/x.py"', '" x.py"', '"x.py "', r'"x\\y.py"', '""'])
def test_path_that_can_never_match_is_rejected(path):
    msg = _error(_map(("card", "alice", path)))
    assert 'module "card"' in msg


@pytest.mark.parametrize("text, fragment", [
    ("modules:\n  - owner: alice\n    paths: [x/]\n", 'module #1: missing "name"'),
    ("modules:\n  - name: card\n    paths: [x/]\n", 'module "card": missing "owner"'),
    ("modules:\n  - name: card\n    owner: alice\n", 'module "card": "paths" must be a non-empty list'),
    ("modules:\n  - name: card\n    owner: alice\n    paths: []\n", 'module "card": "paths"'),
    ("modules:\n  - just-a-string\n", "module #1"),
])
def test_missing_fields_name_the_module(text, fragment):
    assert fragment in _error(text)


def test_wrong_top_level_key_still_fails():
    with pytest.raises(ModuleMapError):
        parse_modules("module:\n  - name: a\n    owner: b\n    paths: [x/]\n")


# ---- folder written without the trailing "/" ----

def test_folder_without_slash_is_rejected_when_a_file_inside_changes():
    modules = [{"name": "detect", "owner": "alice", "paths": ["changesignal"]}]
    with pytest.raises(ModuleMapError) as exc:
        find_affected(["changesignal/card.py"], modules, "bob")
    msg = str(exc.value)
    assert 'module "detect"' in msg and '"changesignal/"' in msg and len(msg) <= 100


def test_folder_without_slash_is_rejected_even_for_the_authors_own_module():
    modules = [{"name": "detect", "owner": "alice", "paths": ["changesignal"]}]
    with pytest.raises(ModuleMapError):
        find_affected(["changesignal/card.py"], modules, "alice")


@pytest.mark.parametrize("path, changed", [
    ("Makefile", ["Makefile"]),                       # a real file with no dot
    ("LICENSE", ["LICENSE", "docs/a.md"]),
    ("changesignal", ["README.md"]),                  # folder not touched: nothing is missed
    ("changesignal/", ["changesignal/card.py"]),      # written correctly
    ("changesignal/*", ["changesignal/card.py"]),     # glob
    ("changesignal", ["changesignal2/card.py"]),      # different folder with the same prefix
])
def test_valid_or_harmless_paths_are_not_rejected(path, changed):
    find_affected(changed, [{"name": "m", "owner": "alice", "paths": [path]}], "bob")
