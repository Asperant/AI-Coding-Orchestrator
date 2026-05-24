from __future__ import annotations

from core.safety import guard_text_output


DEFAULT_MAX_CONTEXT_CHARS = 12000
KNOWN_AGENT_ROLES: tuple[str, ...] = (
    "Planner",
    "Reviewer",
    "Tester",
    "Security",
    "Architect",
    "Product",
    "Release",
)
KNOWN_CONTEXT_SOURCES = {
    "task_text",
    "context_text",
    "project_context",
    "diff_text",
    "changed_files",
    "planner_report",
    "edit_plan",
    "codex_prompt_package",
    "memory_sync_summary",
    "approval_gate",
    "git_status",
}
HIGH_RISK_ROLES = {"Security", "Release"}


def _build_safety_requirements(max_context_chars: int) -> list[str]:
    return [
        "LLM-backed agent execution must be explicitly enabled.",
        "Explicit approval confirmation is required before any LLM-backed agent run.",
        "Agent role must be one of: Planner, Reviewer, Tester, Security, Architect, Product, Release.",
        "Task text must pass secret and safety scanning.",
        "Context text must pass secret and safety scanning.",
        f"Context text must not exceed {max_context_chars} characters.",
        "Only known context source labels are allowed.",
        "Deterministic fallback remains available when LLM execution is disabled or blocked.",
        "No LLM, API, tool, or file execution is performed by this contract.",
    ]


def _append_guard_failures(
    blocked_reasons: list[str],
    text: str,
    context_label: str,
) -> None:
    guard_result = guard_text_output(text, context_label)
    if guard_result["allowed"]:
        return

    blocked_reasons.append(str(guard_result["safe_message"]))
    for finding in guard_result["findings"]:
        blocked_reasons.append(str(finding["summary"]))


def _dedupe(items: list[str]) -> list[str]:
    deduped: list[str] = []
    for item in items:
        if item not in deduped:
            deduped.append(item)
    return deduped


def evaluate_llm_agent_contract(
    agent_role: str,
    task_text: str,
    context_text: str | None = None,
    allowed_context_sources: list[str] | tuple[str, ...] | None = None,
    max_context_chars: int | None = None,
    approval_confirmed: bool = False,
    llm_enabled: bool = False,
) -> dict[str, object]:
    blocked_reasons: list[str] = []
    normalized_role = str(agent_role).strip()
    normalized_sources = [str(source).strip() for source in list(allowed_context_sources or []) if str(source).strip()]
    effective_max_context_chars = DEFAULT_MAX_CONTEXT_CHARS if max_context_chars is None else max_context_chars

    if effective_max_context_chars <= 0:
        effective_max_context_chars = DEFAULT_MAX_CONTEXT_CHARS

    if normalized_role not in KNOWN_AGENT_ROLES:
        blocked_reasons.append(f"Unknown agent role: {normalized_role}")

    if not llm_enabled:
        blocked_reasons.append(
            "LLM-backed agent execution is disabled. Deterministic fallback remains available."
        )

    if not approval_confirmed:
        blocked_reasons.append(
            "Explicit approval confirmation is required before any LLM-backed agent run."
        )

    _append_guard_failures(blocked_reasons, task_text, "LLM agent task text")

    normalized_context_text = "" if context_text is None else str(context_text)
    if normalized_context_text:
        _append_guard_failures(blocked_reasons, normalized_context_text, "LLM agent context text")
        if len(normalized_context_text) > effective_max_context_chars:
            blocked_reasons.append(
                f"Context text exceeds the maximum allowed size of {effective_max_context_chars} characters."
            )

    for source in normalized_sources:
        if source not in KNOWN_CONTEXT_SOURCES:
            blocked_reasons.append(f"Unknown context source is not allowed: {source}")

    deduped_blocked_reasons = _dedupe(blocked_reasons)
    can_run_llm_agent = not deduped_blocked_reasons
    risk_level = "high" if normalized_role in HIGH_RISK_ROLES or deduped_blocked_reasons else "medium"
    if normalized_role not in KNOWN_AGENT_ROLES:
        risk_level = "high"

    execution_summary = (
        f"LLM-backed {normalized_role} agent may run under the current contract. "
        "Deterministic fallback remains available."
        if can_run_llm_agent
        else (
            f"LLM-backed {normalized_role or 'agent'} is blocked due to "
            f"{len(deduped_blocked_reasons)} issue(s). Deterministic fallback remains available."
        )
    )

    return {
        "can_run_llm_agent": can_run_llm_agent,
        "approval_required": True,
        "risk_level": risk_level,
        "blocked_reasons": deduped_blocked_reasons or ["none"],
        "allowed_context_sources": normalized_sources or ["none"],
        "safety_requirements": _build_safety_requirements(effective_max_context_chars),
        "fallback_mode": "deterministic",
        "execution_summary": execution_summary,
    }


def format_llm_agent_contract_view(result: dict[str, object]) -> str:
    blocked_reasons = list(result.get("blocked_reasons", [])) or ["none"]
    allowed_context_sources = list(result.get("allowed_context_sources", [])) or ["none"]
    safety_requirements = list(result.get("safety_requirements", [])) or ["none"]

    return "\n".join(
        [
            f"Can run LLM agent: {'yes' if result.get('can_run_llm_agent') else 'no'}",
            f"Approval required: {'yes' if result.get('approval_required') else 'no'}",
            f"Risk level: {result.get('risk_level', 'low')}",
            f"Blocked reasons: {'; '.join(str(item) for item in blocked_reasons)}",
            f"Allowed context sources: {'; '.join(str(item) for item in allowed_context_sources)}",
            f"Safety requirements: {'; '.join(str(item) for item in safety_requirements)}",
            f"Fallback mode: {result.get('fallback_mode', 'deterministic')}",
            f"Execution summary: {result.get('execution_summary', '')}",
        ]
    )


def format_llm_agent_contract(result: dict[str, object]) -> str:
    return format_llm_agent_contract_view(result)
