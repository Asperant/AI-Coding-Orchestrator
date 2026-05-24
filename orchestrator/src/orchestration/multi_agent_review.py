from __future__ import annotations

from agents.agent_runtime import run_agent_workflow
from agents.agent_decision import format_aggregated_decision
from brain.memory_sync import suggest_memory_sync
from orchestration.knowledge_update import (
    format_knowledge_update_with_compatibility,
    generate_knowledge_update_proposal,
)
from orchestration.approval_gate_manager import (
    evaluate_approval_requirements,
    format_approval_gate_view,
)


def _build_next_action(
    is_git_repo: bool,
    diff_present: bool,
    required_fixes: list[str],
) -> str:
    if not is_git_repo:
        return "Run diff review on a git repository with a readable working tree."
    if not diff_present:
        return "Provide a repository state with actual changes before requesting diff review."
    if required_fixes:
        return required_fixes[0]
    return "Review looks clear enough to proceed with targeted tests."


def _build_per_agent_signal_summary(
    workflow_summary: dict[str, object],
) -> list[str]:
    signals: list[str] = []
    for agent_result in list(workflow_summary.get("per_agent_results", [])):
        role = str(agent_result.get("role", "Agent"))
        findings = [
            str(item)
            for item in list(agent_result.get("findings", []))
            if item and item != "none"
        ]
        suggested_tests = [
            str(item)
            for item in list(agent_result.get("suggested_tests", []))
            if item and item != "none"
        ]
        signal_parts: list[str] = []
        if findings:
            signal_parts.append(findings[0])
        if role == "Tester" and suggested_tests:
            signal_parts.append(f"Closest test: {suggested_tests[0]}")
        if role == "Security":
            risks = [
                str(item)
                for item in list(agent_result.get("risks", []))
                if item and item != "none"
            ]
            if risks:
                signal_parts.append(f"Primary risk: {risks[0]}")

        if signal_parts:
            signals.append(f"{role}: {' '.join(signal_parts)}")
    return signals or ["No per-agent review signals were produced."]


def _build_final_decision_reason(
    *,
    decision: str,
    is_git_repo: bool,
    diff_present: bool,
    risks: list[str],
    required_fixes: list[str],
) -> str:
    non_none_risks = [item for item in risks if item != "none"]
    non_none_fixes = [item for item in required_fixes if item != "none"]

    if decision == "Blocked":
        if not is_git_repo:
            return "Blocked because diff review requires a git repository."
        return non_none_fixes[0] if non_none_fixes else "Blocked because the review flow found a hard stop."
    if decision == "Needs more context":
        if not diff_present:
            return "Needs more context because no git diff is available to review."
        return non_none_fixes[0] if non_none_fixes else "Needs more context because the review surface is incomplete."
    if decision == "Needs revision":
        if non_none_risks:
            return f"Needs revision because the highest risk was: {non_none_risks[0]}"
        if non_none_fixes:
            return f"Needs revision because the top required fix was: {non_none_fixes[0]}"
        return "Needs revision because elevated review signals were detected."
    if decision == "Approved with changes":
        if non_none_fixes:
            return f"Approved with changes because the top follow-up is: {non_none_fixes[0]}"
        return "Approved with changes because small follow-up work is still recommended."
    return "Approved because the current diff looks scoped and no blocking review signal was detected."


def generate_multi_agent_diff_review(
    git_state: dict[str, object],
    task_classification: dict[str, object] | None = None,
    project_context: dict[str, object] | None = None,
) -> dict[str, object]:
    is_git_repo = bool(git_state.get("is_git_repo"))
    changed_files = list(git_state.get("changed_files", []))
    diff_text = str(git_state.get("diff_text", ""))
    diff_present = bool(git_state.get("diff_present"))
    workflow_summary = run_agent_workflow(
        task_text="",
        mode="review-diff",
        task_classification=task_classification,
        changed_files=changed_files,
        diff_text=diff_text,
        project_context=project_context,
        is_git_repo=is_git_repo,
        diff_present=diff_present,
    )
    agents_used = list(workflow_summary["agents_used"])
    required_fixes = list(workflow_summary["required_fixes"])
    decision = str(workflow_summary["decision_hint"])
    multi_agent_decision_summary = format_aggregated_decision(workflow_summary.get("multi_agent_decision", {}))

    if not is_git_repo:
        summary = "Diff review cannot run because the project is not a git repository."
    elif not diff_present:
        summary = "No git diff is present, so review context is incomplete."
    else:
        summary = f"Reviewed {len(changed_files)} changed file(s) through rule-based reviewer lenses."

    approval_gate = evaluate_approval_requirements(
        task_classification=task_classification,
        requested_actions=["multi_agent_diff_review"],
    )
    risks = list(workflow_summary["risks"])
    memory_sync_suggestion = suggest_memory_sync(
        "",
        task_classification or {
            "primary_task_type": "unknown",
            "secondary_task_types": [],
            "confidence": "low",
            "risk_level": "low",
            "rationale": "No task classification was provided.",
        },
        planner_summary=summary,
        changed_files=changed_files,
        findings_or_risks=list(workflow_summary["consolidated_findings"]) + risks,
    )
    
    knowledge_update_proposal = generate_knowledge_update_proposal(
        memory_sync_suggestion,
        "",
        findings=list(workflow_summary["consolidated_findings"]),
        suggested_tests=list(workflow_summary["suggested_tests"]),
    )

    per_agent_signal_summary = _build_per_agent_signal_summary(workflow_summary)
    final_decision_reason = _build_final_decision_reason(
        decision=decision,
        is_git_repo=is_git_repo,
        diff_present=diff_present,
        risks=risks,
        required_fixes=required_fixes,
    )

    return {
        "summary": summary,
        "decision": decision,
        "agents_used": agents_used,
        "per_agent_signal_summary": per_agent_signal_summary,
        "changed_files": changed_files or ["none"],
        "key_findings": list(workflow_summary["consolidated_findings"]),
        "risks": risks,
        "required_fixes": required_fixes or ["none"],
        "suggested_tests": list(workflow_summary["suggested_tests"]),
        "final_decision_reason": final_decision_reason,
        "approval_gate": approval_gate,
        "knowledge_update_proposal": knowledge_update_proposal,
        "memory_docs_update_suggestion": memory_sync_suggestion,
        "next_small_action": _build_next_action(is_git_repo, diff_present, required_fixes),
        "multi_agent_decision_summary": multi_agent_decision_summary,
    }


def generate_secret_blocked_diff_review(
    git_state: dict[str, object],
    safety_guard_result: dict[str, object],
    task_classification: dict[str, object] | None = None,
) -> dict[str, object]:
    changed_files = list(git_state.get("changed_files", [])) or ["none"]
    safe_findings = [
        str(finding.get("summary", "Secret-like content detected."))
        for finding in list(safety_guard_result.get("findings", []))
    ] or ["Secret-like content was detected in the diff."]
    approval_gate = evaluate_approval_requirements(
        task_classification=task_classification,
        requested_actions=["multi_agent_diff_review"],
    )
    risks = [
        "Secret-like content in a diff can leak credentials or sensitive access details.",
    ]
    memory_sync_suggestion = suggest_memory_sync(
        "",
        task_classification or {
            "primary_task_type": "unknown",
            "secondary_task_types": [],
            "confidence": "low",
            "risk_level": "low",
            "rationale": "No task classification was provided.",
        },
        planner_summary=str(safety_guard_result.get("safe_message", "")),
        changed_files=changed_files,
        findings_or_risks=safe_findings + risks,
    )
    
    knowledge_update_proposal = generate_knowledge_update_proposal(
        memory_sync_suggestion,
        "",
        findings=safe_findings,
        suggested_tests=[
            "Re-scan the sanitized diff and rerun review after secrets are removed.",
        ],
    )

    return {
        "summary": str(safety_guard_result.get("safe_message", "Diff review output blocked.")),
        "decision": "Blocked",
        "agents_used": ["Reviewer", "Tester", "Security"],
        "per_agent_signal_summary": [
            "Reviewer: Diff output was blocked before normal review because secret-like content was detected.",
            "Tester: Tests were not executed because the diff must be sanitized before review. Closest test: Re-scan the sanitized diff and rerun review after secrets are removed.",
            "Security: Secret-like diff content was blocked to prevent leaking credentials or sensitive access details.",
        ],
        "changed_files": changed_files,
        "key_findings": safe_findings,
        "risks": risks,
        "required_fixes": [
            "Remove or redact the secret-like content before requesting diff review or saving a report.",
        ],
        "suggested_tests": [
            "Re-scan the sanitized diff and rerun review after secrets are removed.",
        ],
        "final_decision_reason": "Blocked because secret-like diff content must be removed or redacted before review can proceed.",
        "approval_gate": approval_gate,
        "knowledge_update_proposal": knowledge_update_proposal,
        "memory_docs_update_suggestion": memory_sync_suggestion,
        "next_small_action": "Sanitize the diff and rerun the review flow.",
        "multi_agent_decision_summary": None,
    }


def _format_section_value(value: object) -> str:
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return str(value)


def format_multi_agent_diff_review(review_report: dict[str, object]) -> str:
    ordered_sections = (
        ("Summary", review_report["summary"]),
        ("Decision", review_report["decision"]),
        ("Final decision reason", review_report["final_decision_reason"]),
        ("Agents used", review_report["agents_used"]),
        ("Per-agent signals", review_report["per_agent_signal_summary"]),
        ("Changed files", review_report["changed_files"]),
        ("Key findings", review_report["key_findings"]),
        ("Risks", review_report["risks"]),
        ("Required fixes", review_report["required_fixes"]),
        ("Suggested tests", review_report["suggested_tests"]),
        ("Approval Gate", format_approval_gate_view(review_report["approval_gate"])),
        (
            "Knowledge Update Proposal",
            "\n"
            + format_knowledge_update_with_compatibility(
                review_report["knowledge_update_proposal"],
                review_report["memory_docs_update_suggestion"],
            ),
        ),
        ("Next small action", review_report["next_small_action"]),
    )
    return "\n".join(f"{label}: {_format_section_value(value)}" for label, value in ordered_sections)
