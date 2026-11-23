"""Impact card generation.  Owner: yixiang0706 (card).

STUB for the walking skeleton: renders a fixed template, no LLM call yet.
TODO (card): send pr["diff"] + `affected` + prompts/impact_card.md to the LLM,
write the "What changed" summary, and detect a missing reason properly
(the PR template text alone should not count as a reason).
"""

KIND_LABEL = {
    "owned_path": "owned path (rule)",
    "possible_caller": "possible caller (AI/static analysis)",
}


def build_card(pr, affected):
    """pr = {"number", "title", "body", "author", "head_sha", "diff"}
    -> {"markdown": str, "reason_missing": bool}
    """
    reason = (pr.get("body") or "").strip()
    reason_missing = not reason

    lines = [
        "### ChangeSignal impact card",
        "",
        "**What changed**",
        "_AI summary not connected yet (walking skeleton)._",
        "",
        "**Author's reason**",
        "> :warning: No reason given. Please explain why this change is needed in the PR description."
        if reason_missing else "See the PR description.",
        "",
        "**Modules that may be affected**",
        "",
    ]
    if affected:
        lines += ["| Module | Owner | How we know | Where |", "|---|---|---|---|"]
        for a in affected:
            where = ", ".join(f"`{f}`" for f in a.get("files", [])) or a.get("location", "")
            lines.append(f"| {a['module']} | @{a['owner']} | {KIND_LABEL.get(a['kind'], a['kind'])} | {where} |")
    else:
        lines.append("No other member's module is touched by this PR.")

    return {"markdown": "\n".join(lines), "reason_missing": reason_missing}
