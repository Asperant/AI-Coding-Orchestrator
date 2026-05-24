from __future__ import annotations

from orchestration.approval_gate_manager import format_approval_gate_view


def _has_blocked_files(edit_plan_result: dict[str, object]) -> bool:
    blocked_files = list(edit_plan_result.get("blocked_files", []))
    if not blocked_files:
        return False
    return not (len(blocked_files) == 1 and blocked_files[0].get("path") == "none")


def _build_safety_rules() -> list[str]:
    return [
        "Only edit the listed allowed files.",
        "Do not perform any broad rewrite or wildcard edit.",
        "Do not add new dependencies unless explicitly approved.",
        "Preserve existing behavior unless the task requires a scoped change.",
        "Stop immediately if secrets or credentials are encountered.",
        "Do not touch AI-Brain.",
        "Do not touch external projects.",
        "Report changed files at the end.",
        "Include manual tests in the final response.",
    ]


def _build_required_verification() -> list[str]:
    return [
        "List the changed files.",
        "Explain how existing behavior was preserved.",
        "Provide manual test steps.",
        "Call out any blocked or uncertain area instead of guessing.",
    ]


def generate_codex_prompt_package(
    task_text: str,
    project_path: str,
    allowed_files: list[str] | tuple[str, ...],
    edit_plan_result: dict[str, object] | None,
    task_classification: dict[str, object] | None = None,
    planner_report_summary: str | None = None,
    approval_confirmed: bool = False,
    pre_codex_agent_guidance: str | None = None,
    ai_brain_guidance: str | None = None,
) -> dict[str, object]:
    safety_rules = _build_safety_rules()
    required_verification = _build_required_verification()
    approval_gate = {} if edit_plan_result is None else dict(edit_plan_result.get("approval_gate", {}))

    if edit_plan_result is None:
        return {
            "can_generate": False,
            "prompt_text": "",
            "blocked_reason": "Edit plan is required before generating a Codex prompt package.",
            "allowed_files": [],
            "approval_gate": approval_gate,
            "safety_rules": safety_rules,
            "required_verification": required_verification,
        }

    normalized_allowed_files = [
        file_path
        for file_path in list(allowed_files)
        if file_path and file_path != "none"
    ]
    if not normalized_allowed_files:
        return {
            "can_generate": False,
            "prompt_text": "",
            "blocked_reason": "No allowed files were provided for a scoped Codex prompt.",
            "allowed_files": [],
            "approval_gate": approval_gate,
            "safety_rules": safety_rules,
            "required_verification": required_verification,
        }

    if _has_blocked_files(edit_plan_result):
        return {
            "can_generate": False,
            "prompt_text": "",
            "blocked_reason": "Edit plan contains blocked files and cannot produce a safe Codex prompt.",
            "allowed_files": normalized_allowed_files,
            "approval_gate": approval_gate,
            "safety_rules": safety_rules,
            "required_verification": required_verification,
        }

    if edit_plan_result.get("approval_required") and not approval_confirmed:
        return {
            "can_generate": False,
            "prompt_text": "",
            "blocked_reason": "Explicit confirmation is required before generating a Codex prompt for edit work.",
            "allowed_files": normalized_allowed_files,
            "approval_gate": approval_gate,
            "safety_rules": safety_rules,
            "required_verification": required_verification,
        }

    task_type = "unknown" if task_classification is None else task_classification.get("primary_task_type", "unknown")
    approval_summary = format_approval_gate_view(approval_gate)
    summary_line = (
        f"Planner summary: {planner_report_summary}"
        if planner_report_summary
        else "Planner summary: not provided."
    )

    prompt_lines = [
        "Codex Task Package",
        f"Task: {task_text}",
        f"Project path: {project_path}",
        f"Task type: {task_type}",
        f"Allowed files: {', '.join(normalized_allowed_files)}",
        summary_line,
        f"Approval gate: {approval_summary}",
    ]
    if approval_confirmed:
        prompt_lines.append("Execution approval status: user already approved this scoped execution.")
        prompt_lines.append("Do not ask for user approval again for this scoped allowed-file edit.")
    if ai_brain_guidance is not None:
        prompt_lines.append(ai_brain_guidance)
    if pre_codex_agent_guidance:
        prompt_lines.append(pre_codex_agent_guidance)
    prompt_lines.append("Constraints:")
    prompt_lines.extend(f"- {rule}" for rule in safety_rules)
    prompt_lines.append("Required verification:")
    prompt_lines.extend(f"- {item}" for item in required_verification)

    return {
        "can_generate": True,
        "prompt_text": "\n".join(prompt_lines),
        "blocked_reason": None,
        "allowed_files": normalized_allowed_files,
        "approval_gate": approval_gate,
        "safety_rules": safety_rules,
        "required_verification": required_verification,
        "pre_codex_agent_guidance": pre_codex_agent_guidance or "",
        "ai_brain_guidance": ai_brain_guidance or "",
    }


def format_codex_prompt_package(result: dict[str, object]) -> str:
    lines = [
        f"Can generate: {'yes' if result.get('can_generate') else 'no'}",
        f"Allowed files: {', '.join(result.get('allowed_files', [])) or 'none'}",
        f"Approval Gate: {format_approval_gate_view(result.get('approval_gate', {}))}",
        f"AI-Brain Guidance included: {'yes' if result.get('ai_brain_guidance') else 'no'}",
        f"Pre-Codex Agent Guidance included: {'yes' if result.get('pre_codex_agent_guidance') else 'no'}",
        f"Safety rules: {'; '.join(result.get('safety_rules', []))}",
        f"Required verification: {'; '.join(result.get('required_verification', []))}",
    ]

    blocked_reason = result.get("blocked_reason")
    if blocked_reason:
        lines.append(f"Blocked reason: {blocked_reason}")
    else:
        lines.append(f"Prompt text:\n{result.get('prompt_text', '')}")

    return "\n".join(lines)
