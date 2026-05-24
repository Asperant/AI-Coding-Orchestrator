import uuid

from tools.mcp_registry import get_registered_tool


def build_audit_event_from_mcp_decision(
    decision_result: dict[str, object],
    tool_name: str,
    action: str = "registry_check",
    target_summary: str | None = None,
    source: str = "orchestrator",
) -> dict[str, object]:
    tool = decision_result.get("tool")
    if isinstance(tool, dict):
        tool_type = str(tool.get("tool_type", "unknown"))
    else:
        tool_type = "unknown"
        
    return {
        "event_id": str(uuid.uuid4()),
        "tool_name": tool_name,
        "tool_type": tool_type,
        "risk_level": str(decision_result.get("risk_level", "high")),
        "action": action,
        "allowed": bool(decision_result.get("allowed")),
        "blocked": not bool(decision_result.get("allowed")),
        "approval_required": bool(decision_result.get("approval_required")),
        "approval_confirmed": False,
        "reason": str(decision_result.get("blocked_reason") or "allowed"),
        "target_summary": target_summary or "none",
        "source": source,
        "safety_notes": list(decision_result.get("safety_notes", [])),
    }


def build_audit_event_from_controlled_write_result(
    write_result: dict[str, object],
    action: str = "controlled_write",
    source: str = "orchestrator",
) -> dict[str, object]:
    tool_name = str(write_result.get("tool_name", "unknown"))
    tool = get_registered_tool(tool_name)
    tool_type = str(tool.get("tool_type", "unknown")) if tool else "unknown"
    risk_level = str(tool.get("risk_level", "unknown")) if tool else "unknown"
    
    blocked = bool(write_result.get("blocked"))
    preview_only = bool(write_result.get("preview_only"))
    
    reason = str(write_result.get("message") or "executed")
    if preview_only and not blocked:
        reason = "preview generated"
        
    approval_confirmed = bool(write_result.get("approval_confirmed", False))

    return {
        "event_id": str(uuid.uuid4()),
        "tool_name": tool_name,
        "tool_type": tool_type,
        "risk_level": risk_level,
        "action": action,
        "allowed": not blocked,
        "blocked": blocked,
        "approval_required": True,
        "approval_confirmed": approval_confirmed,
        "preview_only": preview_only,
        "executed": bool(write_result.get("executed")),
        "reason": reason,
        "target_summary": str(write_result.get("target_path") or "none"),
        "source": source,
        "safety_notes": list(write_result.get("safety_notes", [])),
    }


def format_mcp_audit_event(event: dict[str, object]) -> str:
    lines = [
        f"Audit Event ID: {event.get('event_id')}",
        f"Tool Name: {event.get('tool_name')}",
        f"Tool Type: {event.get('tool_type')}",
        f"Risk Level: {event.get('risk_level')}",
        f"Action: {event.get('action')}",
        f"Allowed: {'yes' if event.get('allowed') else 'no'}",
        f"Blocked: {'yes' if event.get('blocked') else 'no'}",
        f"Approval Required: {'yes' if event.get('approval_required') else 'no'}",
        f"Approval Confirmed: {'yes' if event.get('approval_confirmed') else 'no'}",
        f"Preview Only: {'yes' if event.get('preview_only') else 'no'}",
        f"Executed: {'yes' if event.get('executed') else 'no'}",
        f"Reason: {event.get('reason')}",
        f"Target Summary: {event.get('target_summary')}",
        f"Source: {event.get('source')}",
    ]
    notes = event.get("safety_notes")
    if notes and isinstance(notes, list):
        lines.append(f"Safety Notes: {'; '.join(notes)}")
    return "\n".join(lines)


def format_mcp_audit_events_compact(events: list[dict[str, object]]) -> str:
    lines = []
    for event in events:
        allowed = "allowed" if event.get("allowed") else "blocked"
        lines.append(f"[{event.get('tool_name')}] {event.get('action')} - {allowed} ({event.get('risk_level')} risk) - {event.get('reason')}")
    return "\n".join(lines)
