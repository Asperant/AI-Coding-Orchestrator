from __future__ import annotations

from typing import Any

from brain.memory_sync import format_memory_decision_view
from core.safety import guard_text_output


WRITE_STATUS_NOT_WRITTEN = "not_written"
DEFAULT_PREVIEW_NOTE = "Preview only: no AI-Brain or project docs write was performed."
TEST_KEYWORDS = (
    "e2e",
    "test",
    "tests",
    "unittest",
    "pytest",
    "verification",
    "regression",
    "ci status",
    "test scenario",
)
RISK_KEYWORDS = (
    "risk",
    "security",
    "secret",
    "scope violation",
    "blocked",
    "approval gate",
    "auth",
    "privacy",
    "database",
)
REUSABLE_KEYWORDS = (
    "pattern",
    "workflow",
    "shared",
    "reusable",
    "foundation",
    "contract",
    "formatter",
    "helper",
    "runtime",
    "adapter",
)


def _normalize_lines(items: list[str] | tuple[str, ...] | None) -> list[str]:
    return [str(item).strip() for item in list(items or []) if str(item).strip() and str(item).strip() != "none"]


def _combined_text(
    task_text: str,
    findings: list[str],
    suggested_tests: list[str],
) -> str:
    return " ".join([task_text, *findings, *suggested_tests]).lower()


def _contains_any(combined_text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in combined_text for keyword in keywords)


def _choose_entry_type(
    *,
    base_entry_type: str,
    combined_text: str,
) -> str:
    if _contains_any(combined_text, TEST_KEYWORDS):
        return "test_scenario"
    if _contains_any(combined_text, RISK_KEYWORDS):
        return "risk"
    if _contains_any(combined_text, REUSABLE_KEYWORDS):
        return "decision"
    if base_entry_type and base_entry_type != "none":
        return base_entry_type
    return "lesson"


def _choose_destination(
    *,
    base_destination: str,
    entry_type: str,
) -> str:
    if base_destination == "none":
        return "none"
    if entry_type in {"test_scenario", "risk"}:
        if base_destination == "project_docs":
            return "project_docs"
        if base_destination in {"ai_brain", "both"}:
            return "both"
        return "project_docs"
    return base_destination


def _suggested_target(destination: str, entry_type: str) -> str:
    if destination == "none":
        return "none"
    if destination == "project_docs":
        if entry_type == "risk":
            return "docs/risk-registry.md"
        if entry_type == "test_scenario":
            return "docs/test-scenarios.md"
        return "docs/project-map.md"
    if destination == "ai_brain":
        if entry_type == "bugfix":
            return "AI-Brain reusable bugfix note"
        if entry_type == "risk":
            return "AI-Brain reusable risk decision"
        if entry_type == "test_scenario":
            return "AI-Brain reusable test pattern note"
        if entry_type == "decision":
            return "AI-Brain reusable engineering notes"
        return "AI-Brain cross-project lesson"
    if entry_type == "risk":
        return "AI-Brain reusable risk decision + docs/risk-registry.md"
    if entry_type == "test_scenario":
        return "AI-Brain reusable test pattern note + docs/test-scenarios.md"
    return "AI-Brain reusable engineering notes + docs/project-map.md"


def _reason_for(destination: str, entry_type: str) -> str:
    if destination == "none":
        return "No durable cross-project or project-specific learning was detected."
    if destination == "ai_brain":
        if entry_type == "decision":
            return "This produced a reusable engineering pattern that should be recorded in AI-Brain."
        if entry_type == "bugfix":
            return "This produced a reusable bugfix lesson that fits AI-Brain."
        return "This produced reusable engineering knowledge that belongs in AI-Brain."
    if destination == "project_docs":
        if entry_type == "risk":
            return "This produced a project-specific risk decision that belongs in the risk registry."
        if entry_type == "test_scenario":
            return "This produced project-specific verification knowledge that belongs in test scenarios."
        return "This produced project-specific knowledge that belongs in project docs."
    if entry_type == "risk":
        return "This produced both reusable risk knowledge and project-specific risk follow-up."
    if entry_type == "test_scenario":
        return "This produced both reusable verification knowledge and project-specific test follow-up."
    return "This produced both reusable engineering knowledge and project-specific follow-up."


def _subject_text(task_text: str, findings: list[str]) -> str:
    if task_text.strip():
        return task_text.strip()
    if findings:
        return findings[0]
    return "this workflow"


def _build_proposed_content(
    *,
    destination: str,
    entry_type: str,
    task_text: str,
    findings: list[str],
    suggested_tests: list[str],
) -> str:
    if destination == "none":
        return "none"

    subject = _subject_text(task_text, findings)
    first_finding = findings[0] if findings else "No additional finding was captured."
    first_test = suggested_tests[0] if suggested_tests else "No specific test follow-up was captured."

    if entry_type == "test_scenario":
        return (
            f"Capture a test scenario for '{subject}' with verification focus on: "
            f"{first_test}. Supporting signal: {first_finding}"
        )
    if entry_type == "risk":
        return (
            f"Capture a risk note for '{subject}' describing: {first_finding}. "
            "Include the expected mitigation or review gate."
        )
    if entry_type == "bugfix":
        return (
            f"Capture a reusable bugfix note for '{subject}' with the key lesson: {first_finding}."
        )
    if entry_type == "decision":
        return (
            f"Capture a reusable engineering decision for '{subject}' with the key pattern: {first_finding}."
        )
    return f"Capture a concise lesson for '{subject}' based on: {first_finding}."


def _guard_field(value: str, context_label: str) -> tuple[str, list[str]]:
    guard_result = guard_text_output(value, context_label)
    if guard_result["allowed"]:
        return value, []
    return str(guard_result["safe_message"]), [
        f"{context_label} was blocked or redacted because secret-like content was detected."
    ]


def generate_knowledge_update_proposal(
    memory_sync_suggestion: dict[str, object],
    task_text: str,
    findings: list[str] | None = None,
    suggested_tests: list[str] | None = None,
) -> dict[str, Any]:
    base_destination = str(memory_sync_suggestion.get("destination", "none"))
    base_entry_type = str(memory_sync_suggestion.get("suggested_entry_type", "none"))
    normalized_findings = _normalize_lines(findings)
    normalized_tests = _normalize_lines(suggested_tests)
    combined_text = _combined_text(task_text, normalized_findings, normalized_tests)

    if base_destination == "none" and not normalized_findings and not normalized_tests and not task_text.strip():
        entry_type = "none"
        destination = "none"
    else:
        entry_type = _choose_entry_type(
            base_entry_type=base_entry_type,
            combined_text=combined_text,
        )
        destination = _choose_destination(
            base_destination=base_destination,
            entry_type=entry_type,
        )

    reason = _reason_for(destination, entry_type)
    proposed_content = _build_proposed_content(
        destination=destination,
        entry_type=entry_type,
        task_text=task_text,
        findings=normalized_findings,
        suggested_tests=normalized_tests,
    )

    safe_reason, reason_notes = _guard_field(reason, "Knowledge update proposal reason")
    safe_content, content_notes = _guard_field(
        proposed_content,
        "Knowledge update proposal content",
    )
    safety_notes = [DEFAULT_PREVIEW_NOTE]
    safety_notes.extend(reason_notes)
    safety_notes.extend(content_notes)
    if destination == "none":
        safety_notes.append("No write target is proposed for this workflow.")

    return {
        "destination": destination,
        "suggested_target": _suggested_target(destination, entry_type),
        "entry_type": entry_type,
        "reason": safe_reason,
        "proposed_content": safe_content,
        "approval_required": destination != "none",
        "write_status": WRITE_STATUS_NOT_WRITTEN,
        "safety_notes": safety_notes,
    }


def summarize_knowledge_update_proposal(proposal: dict[str, Any]) -> str:
    return "; ".join(
        [
            f"Destination: {proposal.get('destination', 'none')}",
            f"Suggested target: {proposal.get('suggested_target', 'none')}",
            f"Entry type: {proposal.get('entry_type', 'none')}",
            f"Write status: {proposal.get('write_status', WRITE_STATUS_NOT_WRITTEN)}",
        ]
    )


def format_knowledge_update_proposal(proposal: dict[str, Any]) -> str:
    lines = [
        "Knowledge Update Proposal:",
        f"- Destination: {proposal.get('destination', 'none')}",
        f"- Suggested target: {proposal.get('suggested_target', 'none')}",
        f"- Entry type: {proposal.get('entry_type', 'none')}",
        f"- Reason: {proposal.get('reason', '')}",
        f"- Proposed content: {proposal.get('proposed_content', 'none')}",
        f"- Approval required: {'yes' if proposal.get('approval_required') else 'no'}",
        f"- Write status: {proposal.get('write_status', WRITE_STATUS_NOT_WRITTEN)}",
        f"- Safety notes: {'; '.join(str(note) for note in proposal.get('safety_notes', []) or ['none'])}",
    ]
    return "\n".join(lines)


def format_knowledge_update_with_compatibility(
    proposal: dict[str, Any],
    memory_sync_suggestion: dict[str, object] | None = None,
) -> str:
    lines = [format_knowledge_update_proposal(proposal)]
    if memory_sync_suggestion is not None:
        lines.append(
            "Memory/docs update suggestion: "
            + format_memory_decision_view(memory_sync_suggestion)
        )
    return "\n".join(lines)
