from __future__ import annotations

import re


REUSABLE_TASK_TYPES = {
    "bug fix",
    "refactor",
    "performance change",
    "AI pipeline change",
    "security/privacy change",
}
PROJECT_DOC_TASK_TYPES = {
    "feature",
    "UI change",
    "database change",
    "release/deploy review",
    "test writing",
}
REUSABLE_KEYWORDS = (
    "root cause",
    "pattern",
    "workflow",
    "guardrail",
    "lesson",
    "decision",
    "reusable",
)
PROJECT_KEYWORDS = (
    "docs/",
    "test scenario",
    "regression",
    "path",
    "module",
)
SAFE_NAME_RE = re.compile(r"[^a-z0-9._-]+")


def _combined_text(
    task_text: str,
    planner_summary: str | None,
    findings_or_risks: list[str] | tuple[str, ...] | None,
) -> str:
    parts = [task_text]
    if planner_summary:
        parts.append(planner_summary)
    if findings_or_risks:
        parts.extend(findings_or_risks)
    return " ".join(part for part in parts if part).lower()


def _has_project_specific_context(
    changed_files: list[str] | tuple[str, ...] | None,
    combined_text: str,
) -> bool:
    if changed_files:
        return True
    return any(keyword in combined_text for keyword in PROJECT_KEYWORDS)


def _has_reusable_learning(
    task_type: str,
    combined_text: str,
    planner_summary: str | None,
    findings_or_risks: list[str] | tuple[str, ...] | None,
) -> bool:
    if task_type in REUSABLE_TASK_TYPES and (planner_summary or findings_or_risks):
        return True
    return any(keyword in combined_text for keyword in REUSABLE_KEYWORDS)


def _suggested_entry_type(
    destination: str,
    task_type: str,
    combined_text: str,
) -> str:
    if destination == "none":
        return "none"
    if "risk" in combined_text or task_type in {"security/privacy change", "database change", "release/deploy review"}:
        return "risk"
    if "test scenario" in combined_text or task_type == "test writing":
        return "test_scenario"
    if task_type == "bug fix":
        return "bugfix"
    if task_type in {"refactor", "feature", "performance change", "AI pipeline change"} or "decision" in combined_text:
        return "decision"
    return "lesson"


def _suggested_target(destination: str, entry_type: str) -> str:
    if destination == "ai_brain":
        return "AI-Brain reusable engineering notes"
    if destination == "project_docs":
        if entry_type == "risk":
            return "docs/risk-registry.md"
        if entry_type == "test_scenario":
            return "docs/test-scenarios.md"
        return "docs/project-map.md"
    if destination == "both":
        if entry_type == "risk":
            return "AI-Brain reusable notes + docs/risk-registry.md"
        if entry_type == "test_scenario":
            return "AI-Brain reusable notes + docs/test-scenarios.md"
        return "AI-Brain reusable notes + docs/project-map.md"
    return "none"


def suggest_memory_sync(
    task_text: str,
    task_classification: dict[str, object],
    planner_summary: str | None = None,
    changed_files: list[str] | tuple[str, ...] | None = None,
    findings_or_risks: list[str] | tuple[str, ...] | None = None,
) -> dict[str, object]:
    task_type = str(task_classification.get("primary_task_type", "unknown"))
    combined_text = _combined_text(task_text, planner_summary, findings_or_risks)
    has_project_specific = _has_project_specific_context(changed_files, combined_text)
    has_reusable = _has_reusable_learning(
        task_type,
        combined_text,
        planner_summary,
        findings_or_risks,
    )

    if task_type == "documentation change" and not changed_files and not planner_summary and not findings_or_risks:
        destination = "none"
        reason = "The task looks trivial and does not suggest durable learning."
    elif has_reusable and has_project_specific:
        destination = "both"
        reason = "The task suggests both reusable learning and project-specific follow-up."
    elif has_reusable:
        destination = "ai_brain"
        reason = "The outcome looks reusable across projects and belongs in AI-Brain."
    elif has_project_specific or task_type in PROJECT_DOC_TASK_TYPES:
        destination = "project_docs"
        reason = "The outcome looks specific to this project and fits project docs."
    else:
        destination = "none"
        reason = "No durable cross-project or project-specific learning was detected."

    entry_type = _suggested_entry_type(destination, task_type, combined_text)

    return {
        "destination": destination,
        "reason": reason,
        "suggested_target": _suggested_target(destination, entry_type),
        "suggested_entry_type": entry_type,
        "approval_required": destination != "none",
    }


def format_memory_sync_suggestion(result: dict[str, object]) -> str:
    return format_memory_decision_view(result)


def summarize_memory_sync_suggestion(result: dict[str, object]) -> str:
    return "; ".join(
        [
            f"Destination: {result.get('destination', 'none')}",
            f"Reason: {result.get('reason', '')}",
            f"Suggested target: {result.get('suggested_target', 'none')}",
            f"Suggested entry type: {result.get('suggested_entry_type', 'none')}",
            f"Approval required: {'yes' if result.get('approval_required') else 'no'}",
        ]
    )


def _sanitize_filename(source_text: str, fallback: str) -> str:
    first_line = next((line.strip() for line in source_text.splitlines() if line.strip()), fallback)
    sanitized = SAFE_NAME_RE.sub("-", first_line.lower()).strip("._-")
    if not sanitized:
        sanitized = fallback
    return f"{sanitized}.md" if not sanitized.endswith(".md") else sanitized


def _ai_brain_memory_type_for_entry(entry_type: str) -> str:
    if entry_type == "bugfix":
        return "bugfix"
    if entry_type in {"decision", "risk"}:
        return "decision"
    if entry_type == "test_scenario":
        return "example"
    return "lesson"


def _proposed_ai_brain_target(
    entry_type: str,
    task_text: str,
    content_summary: str | None,
) -> str | None:
    memory_type = _ai_brain_memory_type_for_entry(entry_type)
    filename_seed = content_summary or task_text or "memory-entry"

    if memory_type == "lesson":
        return "02-Code/Lessons-Learned.md"
    if memory_type == "decision":
        return f"06-Decisions/{_sanitize_filename(filename_seed, 'decision-entry')}"
    return f"07-Examples/{_sanitize_filename(filename_seed, f'{memory_type}-entry')}"


def _proposed_project_docs_target(
    memory_sync_suggestion: dict[str, object],
    entry_type: str,
) -> str | None:
    suggested_target = str(memory_sync_suggestion.get("suggested_target", "none"))
    if suggested_target.startswith("docs/"):
        return suggested_target
    if entry_type == "risk":
        return "docs/risk-registry.md"
    if entry_type == "test_scenario":
        return "docs/test-scenarios.md"
    return "docs/project-map.md"


def _build_ai_brain_command_hint(
    target_path: str,
    entry_type: str,
) -> str:
    memory_type = _ai_brain_memory_type_for_entry(entry_type)
    if memory_type == "lesson":
        return (
            'PYTHONPATH=src python3 src/main.py --write-ai-brain --memory-type lesson '
            '--content "<content-to-review>" --confirm-write --write-mode append'
        )
    relative_path = target_path.split("/", 1)[1]
    return (
        "PYTHONPATH=src python3 src/main.py --write-ai-brain "
        f"--memory-type {memory_type} --memory-path {relative_path} "
        '--content "<content-to-review>" --confirm-write'
    )


def _build_project_docs_command_hint(
    project_path: str | None,
    target_path: str,
) -> str:
    command_project_path = project_path or "<approved-project-path>"
    return (
        "PYTHONPATH=src python3 src/main.py "
        f"--project {command_project_path} --write-project-doc {target_path} "
        '--content "<content-to-review>" --confirm-write'
    )


def build_memory_write_plan(
    memory_sync_suggestion: dict[str, object],
    task_text: str,
    project_path: str | None = None,
    content_summary: str | None = None,
) -> dict[str, object]:
    destination = str(memory_sync_suggestion.get("destination", "none"))
    entry_type = str(memory_sync_suggestion.get("suggested_entry_type", "none"))
    reason = str(memory_sync_suggestion.get("reason", ""))

    if destination == "none":
        return {
            "can_write_plan": False,
            "destinations": [],
            "proposed_ai_brain_target": None,
            "proposed_project_docs_target": None,
            "entry_type": "none",
            "approval_required": False,
            "reason": f"{reason} No write plan is suggested.",
            "next_command_hint": "No write command suggested.",
        }

    proposed_ai_brain_target = None
    proposed_project_docs_target = None
    destinations: list[str] = []
    command_hints: list[str] = []

    if destination in {"ai_brain", "both"}:
        proposed_ai_brain_target = _proposed_ai_brain_target(entry_type, task_text, content_summary)
        if proposed_ai_brain_target is not None:
            destinations.append("ai_brain")
            command_hints.append(_build_ai_brain_command_hint(proposed_ai_brain_target, entry_type))

    if destination in {"project_docs", "both"}:
        proposed_project_docs_target = _proposed_project_docs_target(memory_sync_suggestion, entry_type)
        if proposed_project_docs_target is not None:
            destinations.append("project_docs")
            command_hints.append(_build_project_docs_command_hint(project_path, proposed_project_docs_target))

    can_write_plan = bool(destinations)
    if can_write_plan:
        write_reason = (
            f"{reason} This is a proposal only and still requires explicit approval before any write."
        )
        next_command_hint = " | ".join(command_hints)
    else:
        write_reason = f"{reason} No safe write target could be proposed."
        next_command_hint = "No write command suggested."

    return {
        "can_write_plan": can_write_plan,
        "destinations": destinations,
        "proposed_ai_brain_target": proposed_ai_brain_target,
        "proposed_project_docs_target": proposed_project_docs_target,
        "entry_type": entry_type,
        "approval_required": can_write_plan,
        "reason": write_reason,
        "next_command_hint": next_command_hint,
    }


def format_memory_write_plan(result: dict[str, object]) -> str:
    destinations = result.get("destinations", [])
    if isinstance(destinations, (list, tuple)):
        formatted_destinations = ", ".join(str(item) for item in destinations) if destinations else "none"
    else:
        formatted_destinations = str(destinations)

    return "\n".join(
        [
            f"Can write plan: {'yes' if result.get('can_write_plan') else 'no'}",
            f"Destinations: {formatted_destinations}",
            f"Proposed AI-Brain target: {result.get('proposed_ai_brain_target') or 'none'}",
            f"Proposed project docs target: {result.get('proposed_project_docs_target') or 'none'}",
            f"Entry type: {result.get('entry_type', 'none')}",
            f"Approval required: {'yes' if result.get('approval_required') else 'no'}",
            f"Reason: {result.get('reason', '')}",
            f"Next command hint: {result.get('next_command_hint', 'No write command suggested.')}",
        ]
    )


def format_memory_decision_view(
    suggestion: dict[str, object],
    write_plan: dict[str, object] | None = None,
) -> str:
    lines = [
        f"Destination: {suggestion.get('destination', 'none')}",
        f"Reason: {suggestion.get('reason', '')}",
        f"Suggested target: {suggestion.get('suggested_target', 'none')}",
        f"Suggested entry type: {suggestion.get('suggested_entry_type', 'none')}",
        f"Approval required: {'yes' if suggestion.get('approval_required') else 'no'}",
    ]

    if write_plan is None:
        return "\n".join(lines)

    lines.extend(
        [
            f"Can write plan: {'yes' if write_plan.get('can_write_plan') else 'no'}",
            (
                "Write plan destinations: "
                f"{', '.join(str(item) for item in write_plan.get('destinations', [])) or 'none'}"
            ),
            (
                "Proposed AI-Brain target: "
                f"{write_plan.get('proposed_ai_brain_target') or 'none'}"
            ),
            (
                "Proposed project docs target: "
                f"{write_plan.get('proposed_project_docs_target') or 'none'}"
            ),
            f"Write plan entry type: {write_plan.get('entry_type', 'none')}",
            (
                "Write plan approval required: "
                f"{'yes' if write_plan.get('approval_required') else 'no'}"
            ),
            f"Write plan reason: {write_plan.get('reason', '')}",
            f"Next command hint: {write_plan.get('next_command_hint', 'No write command suggested.')}",
        ]
    )
    return "\n".join(lines)
