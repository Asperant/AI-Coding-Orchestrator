from __future__ import annotations

from pathlib import Path

from core.safety import guard_text_output


DEFAULT_MAX_TOTAL_CHARS = 8000
TRUNCATION_NOTE = "\n[TRUNCATED to fit context budget]"


def _infer_source_type(tool_name: str) -> str:
    if tool_name == "project_knowledge.read":
        return "project_knowledge"
    if tool_name == "error_monitoring.issue.read":
        return "error_monitoring"
    if tool_name == "local.dev_logs.read":
        return "local_log"
    if tool_name.startswith("github."):
        return "github"
    if tool_name.startswith("filesystem."):
        return "file"
    if tool_name.startswith("git."):
        return "git"
    return "mcp"


def _infer_source_name(tool_name: str, source_path: str | None) -> str:
    if source_path:
        return Path(source_path).name or source_path
    return tool_name


def _safe_blocked_content(block: dict[str, object]) -> str:
    reason = str(block.get("reason") or "Content was blocked.")
    source_name = str(block.get("source_name") or "unknown")
    tool_name = str(block.get("tool_name") or "unknown")
    return f"[BLOCKED CONTEXT] source={source_name} tool={tool_name} reason={reason}"


def build_context_block_from_mcp_result(mcp_result: dict[str, object]) -> dict[str, object]:
    tool_name = str(mcp_result.get("tool_name") or "unknown")
    source_path = mcp_result.get("source_path")
    source_path_text = None if source_path in (None, "") else str(source_path)
    source_type = _infer_source_type(tool_name)
    source_name = _infer_source_name(tool_name, source_path_text)

    blocked = bool(mcp_result.get("blocked"))
    message = str(mcp_result.get("message") or "No message provided.")
    output_text = str(mcp_result.get("output_text") or "")

    if blocked:
        content = output_text or f"[BLOCKED CONTEXT] {message}"
        guard_result = guard_text_output(content, "MCP context block")
        if not guard_result["allowed"]:
            content = str(guard_result["safe_message"])
        safe = False
        reason = message
    else:
        guard_result = guard_text_output(output_text, "MCP context block")
        if not guard_result["allowed"]:
            content = str(guard_result["safe_message"])
            blocked = True
            safe = False
            reason = "Secret-like content was detected while building the context block."
        else:
            content = output_text
            safe = True
            reason = "none"

    return {
        "source_type": source_type,
        "source_name": source_name,
        "tool_name": tool_name,
        "source_path": source_path_text,
        "content": content,
        "safe": safe,
        "blocked": blocked,
        "reason": reason,
        "char_count": len(content),
    }


def compact_context_blocks(
    context_blocks: list[dict[str, object]],
    *,
    max_total_chars: int = DEFAULT_MAX_TOTAL_CHARS,
) -> list[dict[str, object]]:
    compacted: list[dict[str, object]] = []
    used_chars = 0
    seen_contents: set[str] = set()

    for block in context_blocks:
        normalized_block = dict(block)
        content = str(normalized_block.get("content") or "")

        if normalized_block.get("blocked"):
            content = _safe_blocked_content(normalized_block)
            normalized_block["safe"] = False

        if content in seen_contents:
            continue

        remaining_chars = max_total_chars - used_chars
        if remaining_chars <= 0:
            break

        if len(content) > remaining_chars:
            if remaining_chars <= len(TRUNCATION_NOTE):
                break
            content = content[: remaining_chars - len(TRUNCATION_NOTE)].rstrip() + TRUNCATION_NOTE

        normalized_block["content"] = content
        normalized_block["char_count"] = len(content)
        compacted.append(normalized_block)
        seen_contents.add(content)
        used_chars += len(content)

    return compacted


def format_context_blocks(context_blocks: list[dict[str, object]]) -> str:
    if not context_blocks:
        return "Context blocks: none"

    lines = [f"Context blocks: {len(context_blocks)}"]
    for block in context_blocks:
        status = "blocked" if block.get("blocked") else ("safe" if block.get("safe") else "unsafe")
        preview = str(block.get("content") or "").replace("\n", " ")
        preview = preview[:120]
        lines.append(
            "- "
            + f"source={block.get('source_name') or 'unknown'} | "
            + f"tool={block.get('tool_name') or 'unknown'} | "
            + f"status={status} | "
            + f"chars={block.get('char_count') or 0} | "
            + f"preview={preview}"
        )
    return "\n".join(lines)
