"""Impact card generation.  Owner: yixiang0706 (card).

The module list on the card is rule-based (always shown). The "what changed / what might
break / questions" parts are drafted by Claude from the diff, the affected modules and the
possible callers. If the AI call fails or no API key is set, the card is still posted
without the AI parts: the AI only explains, it never decides whether a PR can merge.
"""
import json
import os
from pathlib import Path

MODEL = "claude-opus-5-5"
PROMPT = (Path(__file__).parent / "prompts" / "impact_card.md").read_text(encoding="utf-8")
MAX_DIFF_CHARS = 150_000  # beyond this we send the start of the diff and say so on the card
MAX_ROWS = 25             # module table rows shown on the card; the rest are counted
MAX_FIELD_CHARS = 600     # per AI-written text field
MAX_CARD_CHARS = 60_000   # GitHub rejects comments over 65,536 characters

try:  # rule-based reason check from issue #11 (changesignal/reason.py), used once it exists
    from .reason import has_reason
except ImportError:
    has_reason = None

CARD_SCHEMA = {
    "type": "object",
    "properties": {
        "what_changed": {"type": "string"},
        "reason_given": {"type": "boolean"},
        "impacts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "module": {"type": "string"},
                    "risk": {"type": "string"},
                    "evidence": {"type": "string"},
                },
                "required": ["module", "risk", "evidence"],
                "additionalProperties": False,
            },
        },
        "questions_for_owner": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["what_changed", "reason_given", "impacts", "questions_for_owner"],
    "additionalProperties": False,
}

LABELS = {
    "en": {
        "language": "English",
        "title": "ChangeSignal impact card",
        "what": "What changed",
        "ai": "AI draft, may be wrong",
        "reason": "Author's reason",
        "reason_ok": "Given in the PR description.",
        "reason_missing": ":warning: No reason given. Please explain in the PR description why this change is needed.",
        "reason_unverified": "Not checked: the AI summary is unavailable, so we could not tell whether the description gives a reason.",
        "more_rows": "…and {n} more (see the workflow run log).",
        "cut": "_The card was too long and has been cut._",
        "modules": "Modules that may be affected",
        "cols": "| Module | Owner | How we know | Where |",
        "owned_path": "owned path (rule)",
        "possible_caller": "possible caller (static analysis)",
        "none": "No other member's module is touched by this PR.",
        "risks": "What might break",
        "questions": "Check before approving",
        "no_ai": "AI summary unavailable ({why}). The module list below is rule-based and still complete.",
        "truncated": "The diff was too long; the AI only saw its first {n:,} characters.",
        "footer": "Drafted by Claude ({model}) from the diff and `.changesignal/modules.yml`. "
                  "The AI only explains; the module owner decides by approving or requesting changes.",
    },
    "zh-TW": {
        "language": "Traditional Chinese (Taiwan)",
        "title": "ChangeSignal 影響卡",
        "what": "改了什麼",
        "ai": "AI 草稿，可能有誤",
        "reason": "作者的理由",
        "reason_ok": "已寫在 PR 說明中。",
        "reason_missing": ":warning: 作者沒有說明為什麼需要這個修改，請在 PR 說明中補上。",
        "reason_unverified": "未檢查：AI 摘要無法產生，無法判斷 PR 說明是否寫了理由。",
        "more_rows": "…另有 {n} 筆（請看 workflow 執行紀錄）。",
        "cut": "_影響卡太長，已截斷。_",
        "modules": "可能受影響的模組",
        "cols": "| 模組 | 負責人 | 判斷方式 | 位置 |",
        "owned_path": "負責的路徑（規則）",
        "possible_caller": "可能的呼叫者（靜態分析）",
        "none": "這個 PR 沒有改到其他組員的模組。",
        "risks": "可能壞在哪裡",
        "questions": "核准前請確認",
        "no_ai": "AI 摘要無法產生（{why}）。下方的模組清單由規則產生，仍然完整。",
        "truncated": "diff 太長，AI 只看到前 {n:,} 個字元。",
        "footer": "由 Claude（{model}）根據 diff 與 `.changesignal/modules.yml` 草擬。"
                  "AI 只負責說明，是否接受由模組負責人 approve 或 request changes 決定。",
    },
}


def _labels():
    return LABELS.get(os.environ.get("CHANGESIGNAL_LANG", "en"), LABELS["en"])


def _user_message(pr, affected, language):
    diff = pr.get("diff") or ""
    truncated = len(diff) > MAX_DIFF_CHARS
    data = {
        "write_in_language": language,
        "pr": {"title": pr.get("title", ""), "author": pr.get("author", ""),
               "description": pr.get("body") or ""},
        "affected_modules": [
            {"module": a["module"], "owner": a["owner"], "files": a.get("files", [])}
            for a in affected if a["kind"] == "owned_path"],
        "possible_callers": [
            {"module": a["module"], "owner": a["owner"], "symbol": a.get("symbol"),
             "location": a.get("location"), "snippet": a.get("snippet", "")}
            for a in affected if a["kind"] == "possible_caller"],
        "diff_truncated": truncated,
    }
    text = ("Write the impact card for this pull request.\n\n"
            f"<data>\n{json.dumps(data, ensure_ascii=False, indent=2)}\n</data>\n\n"
            f"<diff>\n{diff[:MAX_DIFF_CHARS]}\n</diff>")
    return text, truncated


def ai_draft(pr, affected, client=None):
    """Ask Claude for the card text. Returns (draft dict or None, why-not message or None)."""
    if client is None:
        if not (os.environ.get("ANTHROPIC_API_KEY") or "").strip():
            return None, "no API key configured"
        import anthropic
        client = anthropic.Anthropic()
    import anthropic

    text, truncated = _user_message(pr, affected, _labels()["language"])
    try:
        resp = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",  # if the model declines, the API retries on a fallback model
            system=PROMPT,
            output_config={"effort": "medium",
                           "format": {"type": "json_schema", "schema": CARD_SCHEMA}},
            messages=[{"role": "user", "content": text}],
        )
    except anthropic.APIError as e:
        print(f"::warning::Claude API call failed: {type(e).__name__}: {e}")
        return None, f"API error: {type(e).__name__}"
    if resp.stop_reason != "end_turn":
        print(f"::warning::Claude stopped with stop_reason={resp.stop_reason}")
        return None, f"model stopped early ({resp.stop_reason})"
    try:
        draft = json.loads(next(b.text for b in resp.content if b.type == "text"))
    except (StopIteration, json.JSONDecodeError):
        return None, "unreadable AI response"
    if not _valid_draft(draft):
        return None, "unreadable AI response"
    draft["_truncated"] = truncated
    draft["_model"] = getattr(resp, "model", MODEL)
    return draft, None


def _valid_draft(d):
    """The structured-output schema should guarantee this shape; check anyway, so a surprise
    (e.g. `null`) leads to the card without AI parts instead of a crash."""
    def strs(xs):
        return isinstance(xs, list) and all(isinstance(x, str) for x in xs)
    return (isinstance(d, dict) and isinstance(d.get("what_changed"), str)
            and isinstance(d.get("reason_given"), bool)
            and isinstance(d.get("impacts"), list)
            and all(isinstance(i, dict) and all(isinstance(i.get(k), str) for k in ("module", "risk", "evidence"))
                    for i in d["impacts"])
            and strs(d.get("questions_for_owner")))


def _plain(text, limit=MAX_FIELD_CHARS):
    """Render AI-written text as one plain line, so it cannot open a code fence, a heading,
    a table or HTML that would hide the rule-based part of the card."""
    text = " ".join(str(text).split())
    if len(text) > limit:
        text = text[:limit - 1] + "…"
    text = text.replace("<", "&lt;").replace(">", "&gt;").replace("|", "\\|")
    if text[:1] in ("#", "-", "*", "+", "=", "`", "~", "\\") or text.split(".", 1)[0].isdigit():
        text = "\\" + text  # would otherwise start a heading, list, code fence or numbered list
    return text


def _cell(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def build_card(pr, affected, client=None):
    """pr = {"number", "title", "body", "author", "head_sha", "diff"}
    -> {"markdown": str, "reason_missing": bool}
    """
    L = _labels()
    draft, why_not = ai_draft(pr, affected, client)

    body = pr.get("body") or ""
    if draft is not None:
        reason = "given" if draft["reason_given"] else "missing"
    elif has_reason is not None:
        reason = "given" if has_reason(body) else "missing"
    else:  # without the AI we only know that an empty description gives no reason
        reason = "missing" if not body.strip() else "unverified"
    reason_missing = reason == "missing"

    lines = [f"### {L['title']}", "", f"**{L['what']}** _({L['ai']})_"]
    if draft:
        lines.append(_plain(draft["what_changed"]))
        if draft.get("_truncated"):
            lines.append(f"> {L['truncated'].format(n=MAX_DIFF_CHARS)}")
    else:
        lines.append(f"_{L['no_ai'].format(why=why_not)}_")

    reason_label = {"given": "reason_ok", "missing": "reason_missing", "unverified": "reason_unverified"}[reason]
    lines += ["", f"**{L['reason']}**", L[reason_label], "", f"**{L['modules']}**", ""]
    if affected:
        lines += [L["cols"], "|---|---|---|---|"]
        for a in affected[:MAX_ROWS]:
            where = a.get("location") or ", ".join(f"`{f}`" for f in a.get("files", []))
            how = L.get(a["kind"], a["kind"])
            if a["kind"] == "possible_caller" and a.get("symbol"):
                how += f": `{a['symbol']}`"
            lines.append(f"| {_cell(a['module'])} | @{a['owner']} | {how} | {_cell(where)} |")
        if len(affected) > MAX_ROWS:
            lines += ["", L["more_rows"].format(n=len(affected) - MAX_ROWS)]
    else:
        lines.append(L["none"])

    if draft and draft.get("impacts"):
        lines += ["", f"**{L['risks']}** _({L['ai']})_"]
        for i in draft["impacts"]:
            lines.append(f"- **{_plain(i['module'], 80)}**: {_plain(i['risk'])} ({_plain(i['evidence'], 200)})")
    if draft and draft.get("questions_for_owner"):
        lines += ["", f"**{L['questions']}** _({L['ai']})_"]
        lines += [f"- [ ] {_plain(q, 300)}" for q in draft["questions_for_owner"][:3]]
    if draft:
        lines += ["", f"<sub>{L['footer'].format(model=draft['_model'])}</sub>"]

    markdown = "\n".join(lines)
    if len(markdown) > MAX_CARD_CHARS:
        markdown = markdown[:MAX_CARD_CHARS] + "\n\n" + L["cut"]
    return {"markdown": markdown, "reason_missing": reason_missing}
