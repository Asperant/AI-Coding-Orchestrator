from __future__ import annotations


HIGH_RISK_TASK_TYPES = {
    "security/privacy change",
    "database change",
    "release/deploy review",
}

READ_ONLY_ACTIONS = {
    "status",
    "project_context_check",
    "task_classification",
    "planner_report",
    "git_status_read",
    "git_diff_read",
    "multi_agent_diff_review",
    "save_report",
    "save_report_inside_app_reports_dir",
}

ACTION_RULES = {
    "file_edit": ("medium", "File edits change repository state and require explicit approval."),
    "broad_rewrite": ("high", "Broad rewrites are high-risk and need explicit approval."),
    "new_dependency": ("high", "New dependencies change supply-chain and runtime risk."),
    "delete": ("high", "Delete actions are destructive and require explicit approval."),
    "move": ("high", "Move actions change file locations and require explicit approval."),
    "rename": ("high", "Rename actions change file locations and require explicit approval."),
    "database_migration": ("high", "Database migrations require explicit approval before execution."),
    "production_config_change": (
        "high",
        "Production config changes require explicit approval before proceeding.",
    ),
    "destructive_command": (
        "high",
        "Destructive commands require explicit approval before they can run.",
    ),
    "release_deploy_action": (
        "high",
        "Release or deploy actions require explicit approval before proceeding.",
    ),
    "ai_brain_write": ("high", "Writing to AI-Brain requires explicit approval."),
    "project_docs_write": ("medium", "Writing to project docs requires explicit approval."),
    "mcp_write": ("high", "MCP write or destructive tool use requires explicit approval."),
    "mcp_destructive": ("high", "MCP destructive tool use requires explicit approval."),
    "codex_execution": ("high", "Codex execution requests require explicit approval."),
}

ACTION_ALIASES = {
    "broad-rewrite": "broad_rewrite",
    "new-dependency": "new_dependency",
    "database-migration": "database_migration",
    "production-config-change": "production_config_change",
    "destructive-command": "destructive_command",
    "release-deploy-action": "release_deploy_action",
    "release_deploy": "release_deploy_action",
    "deploy": "release_deploy_action",
    "ai-brain-write": "ai_brain_write",
    "project-docs-write": "project_docs_write",
    "mcp-destructive-tool-use": "mcp_destructive",
    "mcp_destructive_tool_use": "mcp_destructive",
    "mcp-write": "mcp_write",
    "mcp-destructive": "mcp_destructive",
    "mcp_destructive": "mcp_destructive",
    "codex-execution": "codex_execution",
}


def _normalize_action(action: str) -> str:
    normalized = action.strip().lower().replace(" ", "_").replace("-", "_")
    return ACTION_ALIASES.get(normalized, normalized)


def _risk_rank(risk_level: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}[risk_level]


def _update_risk(current_risk: str, candidate_risk: str) -> str:
    if _risk_rank(candidate_risk) > _risk_rank(current_risk):
        return candidate_risk
    return current_risk


def _record_requirement(
    result: dict[str, object],
    risk_level: str,
    reason: str,
    blocked_action: str | None = None,
) -> None:
    result["approval_required"] = True
    result["risk_level"] = _update_risk(str(result["risk_level"]), risk_level)

    reasons = result["reasons"]
    if reason not in reasons:
        reasons.append(reason)

    if blocked_action is not None:
        blocked_actions = result["blocked_actions"]
        if blocked_action not in blocked_actions:
            blocked_actions.append(blocked_action)


def _evaluate_task_classification(
    result: dict[str, object],
    task_classification: dict[str, object] | None,
) -> None:
    if task_classification is None:
        return

    task_types = {
        task_classification.get("primary_task_type"),
        *list(task_classification.get("secondary_task_types", [])),
    }

    if "security/privacy change" in task_types:
        _record_requirement(
            result,
            "high",
            "Security-sensitive tasks require explicit approval before implementation.",
            "implementation_change",
        )
    if "database change" in task_types:
        _record_requirement(
            result,
            "high",
            "Database-related tasks require explicit approval before implementation.",
            "implementation_change",
        )
    if "release/deploy review" in task_types:
        _record_requirement(
            result,
            "high",
            "Release or deploy tasks require explicit approval before implementation.",
            "implementation_change",
        )


def _evaluate_requested_actions(
    result: dict[str, object],
    requested_actions: list[str],
) -> None:
    for action in requested_actions:
        normalized_action = _normalize_action(action)
        if normalized_action in READ_ONLY_ACTIONS:
            continue

        action_rule = ACTION_RULES.get(normalized_action)
        if action_rule is None:
            continue

        risk_level, reason = action_rule
        _record_requirement(result, risk_level, reason, normalized_action)


def _evaluate_changed_files(
    result: dict[str, object],
    changed_files: list[str],
) -> None:
    for changed_file in changed_files:
        normalized_path = changed_file.strip().lower().replace("\\", "/")
        if "/ai-brain/" in normalized_path or normalized_path.startswith("ai-brain/"):
            _record_requirement(
                result,
                "high",
                "Writing to AI-Brain requires explicit approval.",
                "ai_brain_write",
            )
        if normalized_path == "agents.md" or normalized_path.startswith("docs/"):
            _record_requirement(
                result,
                "medium",
                "Writing to project docs requires explicit approval.",
                "project_docs_write",
            )


def _build_confirmation(result: dict[str, object]) -> str:
    blocked_actions = list(result["blocked_actions"])
    if not result["approval_required"]:
        return "No additional user approval is required for the requested read-only actions."
    if blocked_actions:
        return (
            "Request explicit user approval before proceeding with: "
            f"{', '.join(blocked_actions)}."
        )
    return "Request explicit user approval before proceeding with this high-risk task."


def evaluate_approval_requirements(
    task_classification: dict[str, object] | None = None,
    requested_actions: list[str] | None = None,
    changed_files: list[str] | None = None,
    project_context: dict[str, object] | None = None,
) -> dict[str, object]:
    del project_context

    result: dict[str, object] = {
        "approval_required": False,
        "risk_level": "low",
        "reasons": [],
        "blocked_actions": [],
        "recommended_user_confirmation": "",
    }

    _evaluate_task_classification(result, task_classification)
    _evaluate_requested_actions(result, list(requested_actions or []))
    _evaluate_changed_files(result, list(changed_files or []))

    result["recommended_user_confirmation"] = _build_confirmation(result)
    return result


def format_approval_requirements(result: dict[str, object]) -> str:
    reasons = list(result.get("reasons", [])) or ["none"]
    blocked_actions = list(result.get("blocked_actions", [])) or ["none"]
    approval_required = "yes" if result.get("approval_required") else "no"

    return "\n".join(
        [
            f"Approval required: {approval_required}",
            f"Risk level: {result.get('risk_level', 'low')}",
            f"Reasons: {'; '.join(reasons)}",
            f"Blocked actions: {', '.join(blocked_actions)}",
            "Recommended user confirmation: "
            f"{result.get('recommended_user_confirmation', '')}",
        ]
    )


def format_approval_gate_view(result: dict[str, object]) -> str:
    return format_approval_requirements(result)


def summarize_approval_requirements(result: dict[str, object]) -> str:
    reasons = list(result.get("reasons", [])) or ["none"]
    blocked_actions = list(result.get("blocked_actions", [])) or ["none"]
    approval_required = "yes" if result.get("approval_required") else "no"

    return "; ".join(
        [
            f"Approval required: {approval_required}",
            f"Risk level: {result.get('risk_level', 'low')}",
            f"Reasons: {', '.join(reasons)}",
            f"Blocked actions: {', '.join(blocked_actions)}",
            "Recommended user confirmation: "
            f"{result.get('recommended_user_confirmation', '')}",
        ]
    )
