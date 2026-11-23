
from pathlib import Path

import pytest

from changesignal.reason import has_reason


OLD_TEMPLATE = """## What this PR does
[One sentence]

## Decision (required if a significant choice was made)
Decision: [what was chosen]
Why: [what problem this solves or what alternative it beat]
Alternative rejected: [optional]
Led by: [name]
"""

NEW_TEMPLATE_EXAMPLE = """## What and why
[One sentence]

## AI assistance
- Tool and model:
- [ ] AI was used

## How I checked it
- [ ] Tests passed

## Risks and alternatives
[Describe risks]
"""


@pytest.mark.parametrize(
    "body, expected",
    [
        (None, False),
        ("", False),
        ("   ", False),
        (OLD_TEMPLATE, False),
        (NEW_TEMPLATE_EXAMPLE, False),
        ("[One sentence]", False),
        ("- [ ] Tests passed", False),
        ("- [x] Tests passed", False),
        ("Led by: 苡翔", False),
        ("Decision:\nWhy:\nLed by:", False),
        ("- Tool and model:", False),
        ("<!-- This is a comment -->", False),
        ("🤖 Generated with [Claude Code](https://claude.ai)", False),
        (
            "## What and why\n"
            "Fix incorrect distance estimation.",
            True,
        ),
        (
            "## What this PR does\n"
            "Prevent incorrect results from small bounding boxes.",
            True,
        ),
        (
            "Fix incorrect distance estimation.",
            True,
        ),
        ("小框會讓分數不準，所以略過", True),
        (
            "## What and why\n"
            "[One sentence]\n\n"
            "## AI assistance\n"
            "Used Claude to generate code.",
            False,
        ),
        (
            "## What and why\n"
            "Improve distance estimation accuracy.\n\n"
            "## AI assistance\n"
            "- [x] AI was used",
            True,
        ),
        ("123456789", False),
        ("1234567890", True),
    ],
)
def test_has_reason(body, expected):
    assert has_reason(body) is expected


def test_repository_pr_template_has_no_reason():
    """The untouched PR template should not count as a reason."""
    root = Path(__file__).resolve().parents[1]
    template = root / ".github" / "pull_request_template.md"

    assert template.is_file(), "PR template file not found"
    body = template.read_text(encoding="utf-8")
    assert has_reason(body) is False
