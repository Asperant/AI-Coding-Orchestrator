from __future__ import annotations

from orchestration.approval_gate_manager import (
    evaluate_approval_requirements,
    format_approval_gate_view,
)


REGISTERED_MCP_TOOLS = {
    "filesystem.read_file": {
        "tool_name": "filesystem.read_file",
        "tool_type": "read",
        "risk_level": "low",
        "approval_required": False,
        "local_only": True,
        "external": False,
        "description": "Read a local file inside approved paths.",
        "runtime_status": "real",
    },
    "git.status": {
        "tool_name": "git.status",
        "tool_type": "read",
        "risk_level": "low",
        "approval_required": False,
        "local_only": True,
        "external": False,
        "description": "Read git working tree status without changing git state.",
        "runtime_status": "real",
    },
    "git.diff": {
        "tool_name": "git.diff",
        "tool_type": "read",
        "risk_level": "medium",
        "approval_required": False,
        "local_only": True,
        "external": False,
        "description": "Read git diff output for review and inspection.",
        "runtime_status": "real",
    },
    "git.log": {
        "tool_name": "git.log",
        "tool_type": "read",
        "risk_level": "low",
        "approval_required": False,
        "local_only": True,
        "external": False,
        "description": "Read commit history without mutating git state.",
        "runtime_status": "real",
    },
    "project_knowledge.read": {
        "tool_name": "project_knowledge.read",
        "tool_type": "read",
        "risk_level": "low",
        "approval_required": False,
        "local_only": True,
        "external": False,
        "description": "Read project docs, notes, or structured project knowledge.",
        "runtime_status": "real",
    },
    "github.issue.read": {
        "tool_name": "github.issue.read",
        "tool_type": "read",
        "risk_level": "medium",
        "approval_required": False,
        "local_only": False,
        "external": True,
        "description": "Read GitHub issue metadata and discussion.",
        "runtime_status": "real",
    },
    "github.pr.read": {
        "tool_name": "github.pr.read",
        "tool_type": "read",
        "risk_level": "medium",
        "approval_required": False,
        "local_only": False,
        "external": True,
        "description": "Read GitHub pull request details and review state.",
        "runtime_status": "real",
    },
    "github.pr.changed_files": {
        "tool_name": "github.pr.changed_files",
        "tool_type": "read",
        "risk_level": "medium",
        "approval_required": False,
        "local_only": False,
        "external": True,
        "description": "Read the changed file list for a GitHub pull request.",
        "runtime_status": "real",
    },
    "github.ci.status": {
        "tool_name": "github.ci.status",
        "tool_type": "read",
        "risk_level": "medium",
        "approval_required": False,
        "local_only": False,
        "external": True,
        "description": "Read GitHub CI or checks status metadata.",
        "runtime_status": "real",
    },
    "test.ci_status.read": {
        "tool_name": "test.ci_status.read",
        "tool_type": "read",
        "risk_level": "medium",
        "approval_required": False,
        "local_only": False,
        "external": True,
        "description": "Read external CI or test status information.",
        "runtime_status": "real_if_configured",
    },
    "notebook.search": {
        "tool_name": "notebook.search",
        "tool_type": "read",
        "risk_level": "medium",
        "approval_required": False,
        "local_only": False,
        "external": True,
        "description": "Search notebook or workspace knowledge sources.",
        "runtime_status": "unavailable",
    },
    "figma.frame.read": {
        "tool_name": "figma.frame.read",
        "tool_type": "read",
        "risk_level": "medium",
        "approval_required": False,
        "local_only": False,
        "external": True,
        "description": "Read Figma frame metadata for design inspection.",
        "runtime_status": "real_if_configured",
    },
    "package.metadata.read": {
        "tool_name": "package.metadata.read",
        "tool_type": "read",
        "risk_level": "low",
        "approval_required": False,
        "local_only": False,
        "external": True,
        "description": "Read package metadata and version availability.",
        "runtime_status": "real",
    },
    "package.manifest.read": {
        "tool_name": "package.manifest.read",
        "tool_type": "read",
        "risk_level": "low",
        "approval_required": False,
        "local_only": True,
        "external": False,
        "description": "Read local dependency manifest from an approved path.",
        "runtime_status": "real",
    },
    "package.changelog.read": {
        "tool_name": "package.changelog.read",
        "tool_type": "read",
        "risk_level": "low",
        "approval_required": False,
        "local_only": False,
        "external": True,
        "description": "Read package changelog entries for a specific version range.",
        "runtime_status": "real (local_changelog), unavailable otherwise",
    },
    "package.advisory.read": {
        "tool_name": "package.advisory.read",
        "tool_type": "read",
        "risk_level": "medium",
        "approval_required": False,
        "local_only": False,
        "external": True,
        "description": "Read known security advisories for a package version.",
        "runtime_status": "real",
    },
    "docs.search": {
        "tool_name": "docs.search",
        "tool_type": "read",
        "risk_level": "low",
        "approval_required": False,
        "local_only": False,
        "external": True,
        "description": "Search local docs or official external documentation sites.",
        "runtime_status": "real",
    },
    "docs.page.read": {
        "tool_name": "docs.page.read",
        "tool_type": "read",
        "risk_level": "low",
        "approval_required": False,
        "local_only": False,
        "external": True,
        "description": "Read a specific local docs file or external documentation page.",
        "runtime_status": "real",
    },
    "figma.component.read": {
        "tool_name": "figma.component.read",
        "tool_type": "read",
        "risk_level": "medium",
        "approval_required": False,
        "local_only": False,
        "external": True,
        "description": "Read properties and variants of a Figma component.",
        "runtime_status": "real_if_configured",
    },
    "figma.tokens.read": {
        "tool_name": "figma.tokens.read",
        "tool_type": "read",
        "risk_level": "low",
        "approval_required": False,
        "local_only": False,
        "external": True,
        "description": "Read extracted design tokens from a Figma file.",
        "runtime_status": "unavailable",
    },
    "error_monitoring.issue.read": {
        "tool_name": "error_monitoring.issue.read",
        "tool_type": "read",
        "risk_level": "medium",
        "approval_required": False,
        "local_only": False,
        "external": True,
        "description": "Read external error monitoring issues or alerts.",
        "runtime_status": "real_if_configured",
    },
    "local.dev_logs.read": {
        "tool_name": "local.dev_logs.read",
        "tool_type": "read",
        "risk_level": "low",
        "approval_required": False,
        "local_only": True,
        "external": False,
        "description": "Read local development logs from approved project paths.",
        "runtime_status": "real",
    },
    "local.dev_logs.search": {
        "tool_name": "local.dev_logs.search",
        "tool_type": "read",
        "risk_level": "low",
        "approval_required": False,
        "local_only": True,
        "external": False,
        "description": "Search local development logs from approved project paths.",
        "runtime_status": "real",
    },
    "report.export": {
        "tool_name": "report.export",
        "tool_type": "write",
        "risk_level": "low",
        "approval_required": True,
        "local_only": True,
        "external": False,
        "description": "Export a generated report to an approved local path.",
        "runtime_status": "real",
    },
    "project_docs.append": {
        "tool_name": "project_docs.append",
        "tool_type": "write",
        "risk_level": "medium",
        "approval_required": True,
        "local_only": True,
        "external": False,
        "description": "Append documentation to an approved project file.",
        "runtime_status": "real",
    },
    "memory.save_proposal": {
        "tool_name": "memory.save_proposal",
        "tool_type": "write",
        "risk_level": "low",
        "approval_required": True,
        "local_only": True,
        "external": False,
        "description": "Preview a proposed memory save to AI-Brain.",
        "runtime_status": "preview_only",
    },
    "github.issue.comment": {
        "tool_name": "github.issue.comment",
        "tool_type": "write",
        "risk_level": "medium",
        "approval_required": True,
        "local_only": False,
        "external": True,
        "description": "Write a GitHub issue comment.",
        "runtime_status": "preview_only",
    },
    "github.pr.summary_update": {
        "tool_name": "github.pr.summary_update",
        "tool_type": "write",
        "risk_level": "medium",
        "approval_required": True,
        "local_only": False,
        "external": True,
        "description": "Update a GitHub pull request summary or body.",
        "runtime_status": "preview_only",
    },
    "destructive.git.reset": {
        "tool_name": "destructive.git.reset",
        "tool_type": "destructive",
        "risk_level": "high",
        "approval_required": True,
        "local_only": True,
        "external": False,
        "description": "Dangerous git reset style action that can discard local changes.",
        "runtime_status": "disabled",
    },
}


def get_registered_tool(tool_name: str) -> dict[str, object] | None:
    tool = REGISTERED_MCP_TOOLS.get(tool_name)
    if tool is None:
        return None
    return dict(tool)


def list_registered_tools(
    *,
    tool_type: str | None = None,
    local_only: bool | None = None,
    external: bool | None = None,
) -> list[dict[str, object]]:
    tools = [dict(tool) for tool in REGISTERED_MCP_TOOLS.values()]
    if tool_type is not None:
        tools = [tool for tool in tools if tool["tool_type"] == tool_type]
    if local_only is not None:
        tools = [tool for tool in tools if bool(tool["local_only"]) is local_only]
    if external is not None:
        tools = [tool for tool in tools if bool(tool["external"]) is external]
    return sorted(tools, key=lambda item: str(item["tool_name"]))


def _approval_gate_for_tool(tool_type: str) -> dict[str, object]:
    if tool_type == "write":
        return evaluate_approval_requirements(requested_actions=["mcp_write"])
    if tool_type == "destructive":
        return evaluate_approval_requirements(requested_actions=["mcp_destructive"])
    return evaluate_approval_requirements()


def evaluate_registered_tool_request(
    tool_name: str,
    requested_type: str,
    approval_confirmed: bool = False,
) -> dict[str, object]:
    tool = get_registered_tool(tool_name)
    if tool is None:
        approval_gate = evaluate_approval_requirements(requested_actions=["mcp_destructive"])
        return {
            "allowed": False,
            "blocked_reason": f"Unknown MCP registry tool: {tool_name}",
            "approval_required": True,
            "risk_level": "high",
            "tool": None,
            "requested_type": requested_type,
            "dangerous": True,
            "approval_gate": approval_gate,
            "safety_notes": [
                "Registry check only: no MCP tool was executed.",
                "Unknown tools stay blocked until they are registered with an explicit capability model.",
            ],
        }

    approval_gate = _approval_gate_for_tool(str(tool["tool_type"]))

    if requested_type != tool["tool_type"]:
        return {
            "allowed": False,
            "blocked_reason": (
                f"Requested MCP tool type mismatch: requested {requested_type}, "
                f"registered {tool['tool_type']}."
            ),
            "approval_required": bool(tool["approval_required"]),
            "risk_level": "high" if tool["tool_type"] == "destructive" else str(tool["risk_level"]),
            "tool": tool,
            "requested_type": requested_type,
            "dangerous": tool["tool_type"] == "destructive",
            "approval_gate": approval_gate,
            "safety_notes": [
                "Registry check only: no MCP tool was executed.",
                "Requested tool type must match the registered capability type exactly.",
            ],
        }

    if tool["tool_type"] == "read":
        return {
            "allowed": True,
            "blocked_reason": None,
            "approval_required": False,
            "risk_level": str(tool["risk_level"]),
            "tool": tool,
            "requested_type": requested_type,
            "dangerous": False,
            "approval_gate": approval_gate,
            "safety_notes": [
                "Registry check only: no MCP tool was executed.",
                "Read-only registry tools may be eligible for future safe integration.",
            ],
        }

    if tool["tool_type"] == "write":
        if not approval_confirmed:
            return {
                "allowed": False,
                "blocked_reason": "Explicit approval is required before allowing a registered MCP write tool.",
                "approval_required": True,
                "risk_level": str(tool["risk_level"]),
                "tool": tool,
                "requested_type": requested_type,
                "dangerous": False,
                "approval_gate": approval_gate,
                "safety_notes": [
                    "Registry check only: no MCP tool was executed.",
                    "Registered write tools require explicit approval before any future integration can run.",
                ],
            }

        return {
            "allowed": True,
            "blocked_reason": None,
            "approval_required": True,
            "risk_level": str(tool["risk_level"]),
            "tool": tool,
            "requested_type": requested_type,
            "dangerous": False,
            "approval_gate": approval_gate,
            "safety_notes": [
                "Registry check only: no MCP tool was executed.",
                "Write tool approval is confirmed, but execution remains disabled in this foundation layer.",
            ],
        }

    if not approval_confirmed:
        return {
            "allowed": False,
            "blocked_reason": "Destructive MCP tools stay blocked until explicit approval is confirmed.",
            "approval_required": True,
            "risk_level": "high",
            "tool": tool,
            "requested_type": requested_type,
            "dangerous": True,
            "approval_gate": approval_gate,
            "safety_notes": [
                "Registry check only: no MCP tool was executed.",
                "Destructive tools are always marked dangerous and high risk.",
            ],
        }

    return {
        "allowed": True,
        "blocked_reason": None,
        "approval_required": True,
        "risk_level": "high",
        "tool": tool,
        "requested_type": requested_type,
        "dangerous": True,
        "approval_gate": approval_gate,
        "safety_notes": [
            "Registry check only: no MCP tool was executed.",
            "Destructive tool approval is confirmed, but real MCP execution is still not enabled.",
        ],
    }


def format_registered_tool_request_result(result: dict[str, object]) -> str:
    tool = result.get("tool")
    tool_name = "unknown" if tool is None else str(tool.get("tool_name", "unknown"))
    tool_type = "unknown" if tool is None else str(tool.get("tool_type", "unknown"))
    local_only = "yes" if tool is not None and tool.get("local_only") else "no"
    external = "yes" if tool is not None and tool.get("external") else "no"
    dangerous = "yes" if result.get("dangerous") else "no"
    description = "not available" if tool is None else str(tool.get("description", "not available"))
    blocked_reason = str(result.get("blocked_reason") or "none")
    approval_gate = result.get("approval_gate") or evaluate_approval_requirements()
    notes = list(result.get("safety_notes", []))

    lines = [
        f"Tool name: {tool_name}",
        f"Registered tool type: {tool_type}",
        f"Requested tool type: {result.get('requested_type') or 'not provided'}",
        f"Allowed: {'yes' if result.get('allowed') else 'no'}",
        f"Blocked reason: {blocked_reason}",
        f"Approval required: {'yes' if result.get('approval_required') else 'no'}",
        f"Risk level: {result.get('risk_level') or 'unknown'}",
        f"Dangerous: {dangerous}",
        f"Local only: {local_only}",
        f"External: {external}",
        f"Description: {description}",
        f"Approval Gate: {format_approval_gate_view(approval_gate)}",
        "Safety notes:",
    ]
    for note in notes:
        lines.append(f"- {note}")
    return "\n".join(lines)


def format_registered_tools_list(tools: list[dict[str, object]]) -> str:
    lines = [f"Registered MCP tools: {len(tools)}"]
    for tool in tools:
        lines.append(
            "- "
            + f"{tool['tool_name']} | type={tool['tool_type']} | risk={tool['risk_level']} | "
            + f"approval_required={'yes' if tool['approval_required'] else 'no'} | "
            + f"local_only={'yes' if tool['local_only'] else 'no'} | "
            + f"external={'yes' if tool['external'] else 'no'}"
        )
    return "\n".join(lines)
