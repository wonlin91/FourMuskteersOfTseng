"""Caller detection on a tiny throwaway repo.  Run: python -m pytest -q"""
import pytest

from changesignal.callers import find_callers

MODULES = [
    {"name": "preprocess", "owner": "Alice", "paths": ["pipeline/preprocess.py", "pipeline/helpers.py"]},
    {"name": "scoring", "owner": "Bob", "paths": ["pipeline/scoring.py"]},
    {"name": "reports", "owner": "Carol", "paths": ["reports/"]},
]

PREPROCESS = """\
import os


THRESHOLD = 0.5


def crop_regions(image, boxes):
    out = []
    for box in boxes:
        out.append(image[box])
    return out


def resize(image):
    return image


class Cropper:
    def run(self, image):
        return crop_regions(image, [])
"""
# Line numbers in PREPROCESS: THRESHOLD 4, crop_regions 7-11, resize 14-15, Cropper 18-20 (run 19-20).

SCORING_TAIL = """


def score(img):
    return {call}(img, [])
"""


def edit(line):
    """A one-line replacement patch on `line`, as GitHub's PR files API returns it."""
    return f"@@ -{line},1 +{line},1 @@\n-old\n+new\n"


def make_repo(tmp_path, files):
    for path, text in {"pipeline/__init__.py": "", "pipeline/preprocess.py": PREPROCESS, **files}.items():
        file = tmp_path / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text, encoding="utf-8")
    return tmp_path


def callers(root, patches, changed=("pipeline/preprocess.py",), **kw):
    return find_callers(list(changed), MODULES, repo_root=str(root), patches=patches, **kw)


@pytest.mark.parametrize("imports, call", [
    ("from pipeline.preprocess import crop_regions", "crop_regions"),
    ("from .preprocess import crop_regions", "crop_regions"),
    ("from .preprocess import crop_regions as crop", "crop"),
    ("import pipeline.preprocess as pp", "pp.crop_regions"),
    ("import pipeline.preprocess", "pipeline.preprocess.crop_regions"),
    ("from pipeline import preprocess", "preprocess.crop_regions"),
    ("from . import preprocess as pre", "pre.crop_regions"),
    ("from pipeline.preprocess import *", "crop_regions"),
])
def test_demo_caller_found_for_each_import_style(tmp_path, imports, call):
    root = make_repo(tmp_path, {"pipeline/scoring.py": imports + SCORING_TAIL.format(call=call)})
    assert callers(root, {"pipeline/preprocess.py": edit(10)}) == [{
        "module": "scoring", "owner": "Bob", "kind": "possible_caller", "symbol": "crop_regions",
        "location": "pipeline/scoring.py:5", "files": ["pipeline/scoring.py"],
        "changed_file": "pipeline/preprocess.py",
        "snippet": f"def score(img):\n    return {call}(img, [])"}]


def test_only_the_changed_function_counts(tmp_path):
    root = make_repo(tmp_path, {"pipeline/scoring.py":
                                "from pipeline.preprocess import resize" + SCORING_TAIL.format(call="resize")})
    assert callers(root, {"pipeline/preprocess.py": edit(10)}) == []
    assert [c["symbol"] for c in callers(root, {"pipeline/preprocess.py": edit(15)})] == ["resize"]


def test_change_outside_any_function_finds_nothing(tmp_path):
    root = make_repo(tmp_path, {"pipeline/scoring.py":
                                "from pipeline.preprocess import crop_regions" + SCORING_TAIL.format(call="crop_regions")})
    assert callers(root, {"pipeline/preprocess.py": edit(4)}) == []


@pytest.mark.parametrize("patches", [None, {}, {"pipeline/preprocess.py": None}])
def test_missing_patch_treats_every_symbol_as_changed(tmp_path, patches):
    root = make_repo(tmp_path, {"pipeline/scoring.py":
                                "from pipeline.preprocess import resize" + SCORING_TAIL.format(call="resize")})
    assert [c["symbol"] for c in callers(root, patches)] == ["resize"]


def test_caller_in_same_module_or_no_module_is_skipped(tmp_path):
    call = "from pipeline.preprocess import crop_regions" + SCORING_TAIL.format(call="crop_regions")
    root = make_repo(tmp_path, {"pipeline/helpers.py": call, "scripts/run.py": call})
    assert callers(root, {"pipeline/preprocess.py": edit(10)}) == []


def test_file_with_syntax_error_is_skipped(tmp_path):
    root = make_repo(tmp_path, {
        "reports/broken.py": "from pipeline.preprocess import crop_regions\ndef (:\n",
        "reports/daily.py": "import pipeline.preprocess as pp\npp.crop_regions(1, [])\n",
    })
    found = callers(root, {"pipeline/preprocess.py": edit(10)})
    assert [c["location"] for c in found] == ["reports/daily.py:2"]
    assert found[0]["module"] == "reports" and found[0]["owner"] == "Carol"
    # Module-level call: snippet is the surrounding lines.
    assert found[0]["snippet"] == "import pipeline.preprocess as pp\npp.crop_regions(1, [])"


def test_deleted_or_non_python_changed_file_is_skipped(tmp_path):
    root = make_repo(tmp_path, {"pipeline/scoring.py": "from pipeline.gone import f\nf()\n"})
    assert callers(root, None, changed=["pipeline/gone.py", "README.md"]) == []


def test_pure_deletion_hunk_touches_the_line_before_the_gap(tmp_path):
    root = make_repo(tmp_path, {"pipeline/scoring.py":
                                "from pipeline.preprocess import crop_regions" + SCORING_TAIL.format(call="crop_regions")})
    inside = "@@ -10,2 +9,0 @@\n-    a = 1\n-    b = 2\n"    # removed after line 9 (inside crop_regions)
    between = "@@ -13,2 +12,0 @@\n-\n-\n"                     # removed after line 12 (blank lines)
    assert [c["symbol"] for c in callers(root, {"pipeline/preprocess.py": inside})] == ["crop_regions"]
    assert callers(root, {"pipeline/preprocess.py": between}) == []


def test_context_lines_do_not_count_as_changes(tmp_path):
    root = make_repo(tmp_path, {"pipeline/scoring.py":
                                "from pipeline.preprocess import resize" + SCORING_TAIL.format(call="resize")})
    # Last line of crop_regions changed; 3 context lines reach into resize but must not mark it.
    patch = "@@ -9,7 +9,7 @@\n     for box in boxes:\n         out.append(image[box])\n-    return 0\n+    return out\n \n \n def resize(image):\n"
    assert callers(root, {"pipeline/preprocess.py": patch}) == []


def test_changed_method_is_reported_as_class_dot_method(tmp_path):
    root = make_repo(tmp_path, {"reports/daily.py": (
        "from pipeline.preprocess import Cropper\n"
        "\n"
        "def build(img):\n"
        "    c = Cropper()\n"
        "    return c.run(img)\n")})
    found = callers(root, {"pipeline/preprocess.py": edit(20)})
    assert [(c["symbol"], c["location"]) for c in found] == [("Cropper.run", "reports/daily.py:5")]


def test_results_sorted_and_one_entry_per_file_and_symbol(tmp_path):
    call = "from pipeline.preprocess import crop_regions\ncrop_regions(1, [])\ncrop_regions(2, [])\n"
    root = make_repo(tmp_path, {"reports/b.py": call, "reports/a.py": call, "pipeline/scoring.py": call})
    found = callers(root, {"pipeline/preprocess.py": edit(10)}, max_snippet_lines=1)
    assert [c["location"] for c in found] == ["pipeline/scoring.py:2", "reports/a.py:2", "reports/b.py:2"]
    assert all(c["snippet"].count("\n") == 0 for c in found)
