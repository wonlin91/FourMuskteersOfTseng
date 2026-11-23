
import re


def has_reason(body: str | None) -> bool:
    """Check whether a PR description contains a meaningful reason."""
    if not body or not body.strip():
        return False

    # 1. Remove HTML comments.
    text = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)

    # 2. If a target section exists, inspect only that section.
    heading = re.search(
        r"(?im)^##[ \t]+(?:What and why|What this PR does)[ \t]*#*[ \t]*$",
        text,
    )
    if heading:
        text = text[heading.end():]
        next_heading = re.search(r"(?m)^#{1,2}[ \t]+\S", text)
        if next_heading:
            text = text[:next_heading.start()]

    meaningful_lines = []

    for line in text.splitlines():
        line = line.strip()

        # 3. Ignore Markdown headings and checkboxes.
        if re.match(r"^#{1,6}\s+", line):
            continue
        if re.match(r"^[-*+]\s+\[[ xX]\]", line):
            continue

        # 4. Ignore generated signatures and metadata.
        if re.match(r"^(?:🤖\s*)?Generated with\b", line, re.I):
            continue
        if re.match(
            r"^(?:[-*+]\s*)?(?:Led by|Tool and model)\s*:",
            line,
            re.I,
        ):
            continue

        # 5. Remove template placeholders.
        line = re.sub(r"\[[^\]\n]*\](?:\([^)]*\))?", "", line)
        line = re.sub(r"^[-*+]\s+", "", line)

        # Remove field labels but keep actual entered values.
        line = re.sub(
            r"^(?:Decision|Why|Alternative rejected)\s*:\s*",
            "",
            line,
            flags=re.IGNORECASE,
        )

        # Ignore empty labels and Markdown separators.
        if re.fullmatch(r"[\w\s/&-]+:\s*", line):
            continue
        if re.fullmatch(r"[-*_~`>|#]+", line):
            continue

        meaningful_lines.append(line)

    # 6. Require at least 10 non-whitespace characters.
    content = re.sub(r"\s", "", " ".join(meaningful_lines))
    return len(content) >= 10
