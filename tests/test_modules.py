import pytest

from changesignal.modules import _matches, find_affected, load_modules


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
