from __future__ import annotations

from core.safety import guard_text_output
from tools.filesystem_gateway import FilesystemGatewayError, read_file
from tools.git_gateway import GitGatewayError, inspect_git_log, inspect_git_state
from tools.mcp_gateway import evaluate_mcp_request


SUPPORTED_LOCAL_READ_TOOLS = {
    "filesystem.read_file",
    "git.status",
    "git.diff",
    "git.log",
}


def _blocked_result(
    *,
    tool_name: str,
    action: str,
    message: str,
    decision: dict[str, object],
    safety_notes: list[str],
    source_path: str | None = None,
) -> dict[str, object]:
    from tools.mcp_audit import build_audit_event_from_mcp_decision
    audit_event = build_audit_event_from_mcp_decision(
        decision, tool_name, action=action, target_summary=source_path
    )
    return {
        "executed": False,
        "blocked": True,
        "tool_name": tool_name,
        "action": action,
        "source_path": source_path,
        "message": message,
        "output_text": "",
        "decision": decision,
        "safety_notes": safety_notes,
        "audit_event": audit_event,
    }


def _executed_result(
    *,
    tool_name: str,
    action: str,
    message: str,
    output_text: str,
    decision: dict[str, object],
    safety_notes: list[str],
    source_path: str | None = None,
) -> dict[str, object]:
    from tools.mcp_audit import build_audit_event_from_mcp_decision
    audit_event = build_audit_event_from_mcp_decision(
        decision, tool_name, action=action, target_summary=source_path
    )
    return {
        "executed": True,
        "blocked": False,
        "tool_name": tool_name,
        "action": action,
        "source_path": source_path,
        "message": message,
        "output_text": output_text,
        "decision": decision,
        "safety_notes": safety_notes,
        "audit_event": audit_event,
    }


def _guard_output(text: str, context_label: str) -> tuple[bool, str, list[str]]:
    guard_result = guard_text_output(text, context_label)
    if guard_result["allowed"]:
        return True, text, []

    findings = [str(item["summary"]) for item in list(guard_result.get("findings", []))]
    return False, str(guard_result["safe_message"]), findings


def run_mcp_read_tool(
    tool_name: str,
    target_path: str | None,
    approved_paths: list[str] | tuple[str, ...] | None,
    *,
    project_path: str | None = None,
) -> dict[str, object]:
    git_project_path = project_path or target_path
    source_path = git_project_path if tool_name.startswith("git.") else target_path
    path_for_decision = git_project_path if tool_name.startswith("git.") else target_path
    decision = evaluate_mcp_request(
        tool_name,
        "read",
        target_path=path_for_decision,
        approved_paths=approved_paths,
    )
    safety_notes = list(decision.get("safety_notes", []))

    if decision["blocked"]:
        return _blocked_result(
            tool_name=tool_name,
            action="read",
            message=str(decision.get("blocked_reason") or "MCP read request was blocked."),
            decision=decision,
            safety_notes=safety_notes,
            source_path=source_path,
        )

    if tool_name not in SUPPORTED_LOCAL_READ_TOOLS:
        safety_notes.append("Only explicitly supported local read MCP tools can execute in this dispatcher.")
        return _blocked_result(
            tool_name=tool_name,
            action="read",
            message=f"Unsupported local MCP read tool: {tool_name}",
            decision=decision,
            safety_notes=safety_notes,
            source_path=source_path,
        )

    if tool_name == "filesystem.read_file":
        if target_path is None:
            safety_notes.append("filesystem.read_file requires --mcp-target-path.")
            return _blocked_result(
                tool_name=tool_name,
                action="read",
                message="filesystem.read_file requires a target path.",
                decision=decision,
                safety_notes=safety_notes,
                source_path=source_path,
            )
        try:
            file_content = read_file(target_path, approved_paths)
        except FilesystemGatewayError as exc:
            return _blocked_result(
                tool_name=tool_name,
                action="read",
                message=str(exc),
                decision=decision,
                safety_notes=safety_notes,
                source_path=source_path,
            )

        allowed, output_text, findings = _guard_output(file_content, "MCP filesystem read output")
        if not allowed:
            safety_notes.extend(findings)
            return _blocked_result(
                tool_name=tool_name,
                action="read",
                message="filesystem.read_file output was blocked because secret-like content was detected.",
                decision=decision,
                safety_notes=safety_notes,
                source_path=source_path,
            ) | {"output_text": output_text}

        return _executed_result(
            tool_name=tool_name,
            action="read",
            message="filesystem.read_file completed successfully.",
            output_text=output_text,
            decision=decision,
            safety_notes=safety_notes,
            source_path=source_path,
        )

    if git_project_path is None:
        safety_notes.append("Git read tools require --project or --mcp-target-path.")
        return _blocked_result(
            tool_name=tool_name,
            action="read",
            message=f"{tool_name} requires a project path.",
            decision=decision,
            safety_notes=safety_notes,
            source_path=source_path,
        )

    try:
        if tool_name == "git.log":
            git_log = inspect_git_log(
                git_project_path,
                approved_paths=list(approved_paths or []),
            )
        else:
            git_state = inspect_git_state(git_project_path, approved_paths=list(approved_paths or []))
    except GitGatewayError as exc:
        return _blocked_result(
            tool_name=tool_name,
            action="read",
            message=str(exc),
            decision=decision,
            safety_notes=safety_notes,
            source_path=source_path,
        )

    if tool_name == "git.status":
        changed_files = list(git_state.get("changed_files", []))
        output_lines = [
            f"Git repo: {'yes' if git_state.get('is_git_repo') else 'no'}",
            f"Status summary: {git_state.get('status_summary') or 'not available'}",
            "Changed files: " + (", ".join(str(item) for item in changed_files) if changed_files else "none"),
        ]
        return _executed_result(
            tool_name=tool_name,
            action="read",
            message="git.status completed successfully.",
            output_text="\n".join(output_lines),
            decision=decision,
            safety_notes=safety_notes,
            source_path=source_path,
        )

    if tool_name == "git.log":
        log_text = str(git_log.get("log_text", ""))
        allowed, output_text, findings = _guard_output(log_text, "MCP git log output")
        if not allowed:
            safety_notes.extend(findings)
            return _blocked_result(
                tool_name=tool_name,
                action="read",
                message="git.log output was blocked because secret-like content was detected.",
                decision=decision,
                safety_notes=safety_notes,
                source_path=source_path,
            ) | {"output_text": output_text}

        return _executed_result(
            tool_name=tool_name,
            action="read",
            message="git.log completed successfully.",
            output_text=output_text,
            decision=decision,
            safety_notes=safety_notes,
            source_path=source_path,
        )

    diff_text = str(git_state.get("diff_text", ""))
    allowed, output_text, findings = _guard_output(diff_text, "MCP git diff output")
    if not allowed:
        safety_notes.extend(findings)
        return _blocked_result(
            tool_name=tool_name,
            action="read",
            message="git.diff output was blocked because secret-like content was detected.",
            decision=decision,
            safety_notes=safety_notes,
            source_path=source_path,
        ) | {"output_text": output_text}

    return _executed_result(
        tool_name=tool_name,
        action="read",
        message="git.diff completed successfully.",
        output_text=output_text,
        decision=decision,
        safety_notes=safety_notes,
        source_path=source_path,
    )


def format_mcp_read_dispatch_result(result: dict[str, object]) -> str:
    output_text = str(result.get("output_text") or "none")
    safety_notes = list(result.get("safety_notes", [])) or ["none"]
    decision = result.get("decision", {})

    return "\n".join(
        [
            f"Tool name: {result.get('tool_name') or 'unknown'}",
            f"Action: {result.get('action') or 'unknown'}",
            f"Executed: {'yes' if result.get('executed') else 'no'}",
            f"Blocked: {'yes' if result.get('blocked') else 'no'}",
            f"Message: {result.get('message') or 'not available'}",
            f"Decision allowed: {'yes' if decision.get('allowed') else 'no'}",
            f"Decision risk level: {decision.get('risk_level') or 'unknown'}",
            f"Output text:\n{output_text}",
            f"Safety notes: {'; '.join(str(note) for note in safety_notes)}",
        ]
    )
