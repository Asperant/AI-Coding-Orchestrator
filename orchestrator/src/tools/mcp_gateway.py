from __future__ import annotations

from core.approved_paths import ApprovedPathError, ensure_approved_path
from orchestration.approval_gate_manager import (
    evaluate_approval_requirements,
    format_approval_gate_view,
)
from tools.mcp_registry import (
    evaluate_registered_tool_request,
    format_registered_tool_request_result,
)


SUPPORTED_TOOL_TYPES = {"read", "write", "destructive"}
FORBIDDEN_BEHAVIOR_MARKERS = (
    "production database",
    "prod database",
    "production db",
    "prod db",
    "database admin",
    "admin database",
    "service key",
    "service-key",
    "service_role",
    "service role",
    "admin key",
    "root key",
)


def _base_result() -> dict[str, object]:
    return {
        "allowed": False,
        "blocked_reason": None,
        "approval_required": False,
        "risk_level": "low",
        "approval_gate": evaluate_approval_requirements(),
        "safety_notes": [],
    }


def _finalize(
    result: dict[str, object],
    *,
    allowed: bool,
    blocked_reason: str | None,
    approval_required: bool,
    risk_level: str,
    approval_gate: dict[str, object],
    safety_notes: list[str],
) -> dict[str, object]:
    result["allowed"] = allowed
    result["blocked_reason"] = blocked_reason
    result["approval_required"] = approval_required
    result["risk_level"] = risk_level
    result["approval_gate"] = approval_gate
    result["safety_notes"] = safety_notes
    return result


def _combined_text(tool_name: str, target_path: str | None) -> str:
    return f"{tool_name} {target_path or ''}".lower()


def _contains_forbidden_behavior(tool_name: str, target_path: str | None) -> bool:
    combined_text = _combined_text(tool_name, target_path)
    if any(marker in combined_text for marker in FORBIDDEN_BEHAVIOR_MARKERS):
        return True
    return "database" in combined_text and ("admin" in combined_text or "production" in combined_text)


def _resolve_target_note(
    target_path: str | None,
    approved_paths: list[str] | tuple[str, ...] | None,
) -> tuple[str | None, str | None]:
    if target_path is None:
        return None, "No target path was provided; path approval was not evaluated."

    try:
        resolved_path = ensure_approved_path(target_path, approved_paths)
    except ApprovedPathError as exc:
        return None, str(exc)

    return str(resolved_path), "Target path is inside approved paths."


def _approval_result_for_tool_type(tool_type: str) -> dict[str, object]:
    if tool_type == "write":
        return evaluate_approval_requirements(requested_actions=["mcp_write"])
    if tool_type == "destructive":
        return evaluate_approval_requirements(requested_actions=["mcp_destructive"])
    return evaluate_approval_requirements()


def evaluate_mcp_tool_request(
    tool_name: str,
    tool_type: str,
    target_path: str | None = None,
    approved_paths: list[str] | tuple[str, ...] | None = None,
    approval_confirmed: bool = False,
) -> dict[str, object]:
    result = _base_result()
    normalized_tool_type = tool_type.strip().lower()
    safety_notes = ["Policy check only: no real MCP tool was executed."]

    if normalized_tool_type not in SUPPORTED_TOOL_TYPES:
        approval_gate = evaluate_approval_requirements(requested_actions=["mcp_destructive"])
        return _finalize(
            result,
            allowed=False,
            blocked_reason=f"Unsupported MCP tool type: {tool_type}",
            approval_required=bool(approval_gate["approval_required"]),
            risk_level=str(approval_gate["risk_level"]),
            approval_gate=approval_gate,
            safety_notes=safety_notes + ["Supported MCP tool types are read, write, and destructive."],
        )

    approval_gate = _approval_result_for_tool_type(normalized_tool_type)

    if _contains_forbidden_behavior(tool_name, target_path):
        return _finalize(
            result,
            allowed=False,
            blocked_reason=(
                "Production database, admin, or service-key MCP behavior is not allowed by policy."
            ),
            approval_required=True,
            risk_level="high",
            approval_gate=evaluate_approval_requirements(requested_actions=["mcp_destructive"]),
            safety_notes=safety_notes + ["High-risk MCP behaviors stay blocked even in policy-check mode."],
        )

    resolved_target_path, path_note = _resolve_target_note(target_path, approved_paths)
    if path_note:
        safety_notes.append(path_note)
    if target_path is not None and resolved_target_path is None:
        return _finalize(
            result,
            allowed=False,
            blocked_reason=path_note,
            approval_required=bool(approval_gate["approval_required"]),
            risk_level=str(approval_gate["risk_level"]),
            approval_gate=approval_gate,
            safety_notes=safety_notes,
        )

    if normalized_tool_type == "read":
        if target_path is None:
            safety_notes.append("Read-only MCP request may proceed only after the actual tool is connected safely.")
        else:
            safety_notes.append("Read-only MCP request is allowed because the target path is approved.")
        return _finalize(
            result,
            allowed=True,
            blocked_reason=None,
            approval_required=bool(approval_gate["approval_required"]),
            risk_level=str(approval_gate["risk_level"]),
            approval_gate=approval_gate,
            safety_notes=safety_notes,
        )

    if normalized_tool_type == "write":
        safety_notes.append("MCP write requests always require explicit approval before any future execution.")
        if target_path is None:
            return _finalize(
                result,
                allowed=False,
                blocked_reason="Write MCP requests require an approved target path.",
                approval_required=bool(approval_gate["approval_required"]),
                risk_level=str(approval_gate["risk_level"]),
                approval_gate=approval_gate,
                safety_notes=safety_notes,
            )
        if not approval_confirmed:
            return _finalize(
                result,
                allowed=False,
                blocked_reason="Explicit approval is required before allowing an MCP write request.",
                approval_required=bool(approval_gate["approval_required"]),
                risk_level=str(approval_gate["risk_level"]),
                approval_gate=approval_gate,
                safety_notes=safety_notes,
            )
        safety_notes.append("Write MCP request passed boundary checks, but no execution was performed.")
        return _finalize(
            result,
            allowed=True,
            blocked_reason=None,
            approval_required=bool(approval_gate["approval_required"]),
            risk_level=str(approval_gate["risk_level"]),
            approval_gate=approval_gate,
            safety_notes=safety_notes,
        )

    safety_notes.append("Destructive MCP requests default to blocked unless explicit approval is confirmed.")
    if target_path is None:
        return _finalize(
            result,
            allowed=False,
            blocked_reason="Destructive MCP requests require an approved target path.",
            approval_required=bool(approval_gate["approval_required"]),
            risk_level=str(approval_gate["risk_level"]),
            approval_gate=approval_gate,
            safety_notes=safety_notes,
        )
    if not approval_confirmed:
        return _finalize(
            result,
            allowed=False,
            blocked_reason="Destructive MCP requests stay blocked until explicit approval is confirmed.",
            approval_required=bool(approval_gate["approval_required"]),
            risk_level=str(approval_gate["risk_level"]),
            approval_gate=approval_gate,
            safety_notes=safety_notes,
        )

    safety_notes.append("Destructive MCP request passed boundary checks, but no execution was performed.")
    return _finalize(
        result,
        allowed=True,
        blocked_reason=None,
        approval_required=bool(approval_gate["approval_required"]),
        risk_level=str(approval_gate["risk_level"]),
        approval_gate=approval_gate,
        safety_notes=safety_notes,
    )


def format_mcp_tool_request_result(result: dict[str, object]) -> str:
    safety_notes = list(result.get("safety_notes", [])) or ["none"]

    return "\n".join(
        [
            f"Allowed: {'yes' if result.get('allowed') else 'no'}",
            f"Blocked reason: {result.get('blocked_reason') or 'none'}",
            f"Approval Gate: {format_approval_gate_view(result.get('approval_gate', {}))}",
            f"Safety notes: {'; '.join(str(note) for note in safety_notes)}",
        ]
    )


def evaluate_mcp_request(
    tool_name: str,
    tool_type: str,
    target_path: str | None = None,
    approved_paths: list[str] | tuple[str, ...] | None = None,
    approval_confirmed: bool = False,
) -> dict[str, object]:
    registry_result = evaluate_registered_tool_request(
        tool_name,
        tool_type,
        approval_confirmed=approval_confirmed,
    )

    if not registry_result["allowed"]:
        return {
            "allowed": False,
            "blocked": True,
            "tool_name": tool_name,
            "tool_type": tool_type,
            "risk_level": str(registry_result["risk_level"]),
            "approval_required": bool(registry_result["approval_required"]),
            "blocked_reason": str(registry_result["blocked_reason"] or "Registry blocked the MCP request."),
            "registry_status": "blocked",
            "gateway_status": "not run",
            "approval_gate": registry_result["approval_gate"],
            "registry_result": registry_result,
            "gateway_result": None,
            "safety_notes": list(registry_result.get("safety_notes", []))
            + ["Unified MCP decision stopped at the registry layer."],
        }

    gateway_result = evaluate_mcp_tool_request(
        tool_name,
        tool_type,
        target_path=target_path,
        approved_paths=approved_paths,
        approval_confirmed=approval_confirmed,
    )

    return {
        "allowed": bool(gateway_result["allowed"]),
        "blocked": not bool(gateway_result["allowed"]),
        "tool_name": tool_name,
        "tool_type": tool_type,
        "risk_level": str(
            "high"
            if tool_type == "destructive"
            else gateway_result.get("risk_level", registry_result["risk_level"])
        ),
        "approval_required": bool(
            registry_result["approval_required"] or gateway_result["approval_required"]
        ),
        "blocked_reason": gateway_result.get("blocked_reason"),
        "registry_status": "passed",
        "gateway_status": "passed" if gateway_result["allowed"] else "blocked",
        "approval_gate": gateway_result["approval_gate"],
        "registry_result": registry_result,
        "gateway_result": gateway_result,
        "safety_notes": list(registry_result.get("safety_notes", []))
        + list(gateway_result.get("safety_notes", []))
        + ["Unified MCP decision combined registry metadata with gateway policy checks."],
    }


def format_mcp_request_result(result: dict[str, object]) -> str:
    safety_notes = list(result.get("safety_notes", [])) or ["none"]

    return "\n".join(
        [
            f"Tool name: {result.get('tool_name') or 'unknown'}",
            f"Tool type: {result.get('tool_type') or 'unknown'}",
            f"Allowed: {'yes' if result.get('allowed') else 'no'}",
            f"Blocked: {'yes' if result.get('blocked') else 'no'}",
            f"Blocked reason: {result.get('blocked_reason') or 'none'}",
            f"Risk level: {result.get('risk_level') or 'unknown'}",
            f"Approval required: {'yes' if result.get('approval_required') else 'no'}",
            f"Registry status: {result.get('registry_status') or 'unknown'}",
            f"Gateway status: {result.get('gateway_status') or 'unknown'}",
            f"Approval Gate: {format_approval_gate_view(result.get('approval_gate', {}))}",
            f"Safety notes: {'; '.join(str(note) for note in safety_notes)}",
        ]
    )
