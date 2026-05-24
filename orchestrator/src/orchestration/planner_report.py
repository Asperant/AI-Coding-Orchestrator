from __future__ import annotations

import re

from brain.memory_sync import suggest_memory_sync
from orchestration.knowledge_update import (
    format_knowledge_update_with_compatibility,
    generate_knowledge_update_proposal,
)
from orchestration.approval_gate_manager import (
    evaluate_approval_requirements,
    format_approval_gate_view,
)


DOC_INSPECTION_PRIORITY = (
    "AGENTS.md",
    "docs/architecture.md",
    "docs/product-context.md",
    "docs/project-map.md",
    "docs/risk-registry.md",
    "docs/test-scenarios.md",
    "docs/quality-gates.md",
)

TASK_TYPE_RISKS = {
    "project assessment": [
        "Starting implementation too early can create unnecessary scope or rework.",
        "Project assessment is safer when docs, entrypoints, and test surfaces are inspected first.",
    ],
    "feature": [
        "New behavior can expand scope and affect nearby flows.",
        "User-facing success, error, and empty states should be checked.",
    ],
    "bug fix": [
        "Fixes can regress adjacent behavior if the root cause is misidentified.",
        "A reproduce-first approach is safer than patching symptoms.",
    ],
    "refactor": [
        "Behavior drift is the main risk during refactors.",
        "Public interfaces and existing call sites should be verified carefully.",
    ],
    "test writing": [
        "Tests can become too implementation-specific if they do not target behavior.",
    ],
    "database change": [
        "Schema and data-access changes can affect correctness and rollback safety.",
        "Access-control and data-shape assumptions should be verified explicitly.",
    ],
    "UI change": [
        "UI work can break loading, error, or small-screen states.",
    ],
    "AI pipeline change": [
        "Fallback, timeout, and output-shape regressions are common in AI paths.",
    ],
    "security/privacy change": [
        "Permission boundaries and sensitive data handling need careful review.",
        "A small mistake can expose secrets or user data.",
    ],
    "performance change": [
        "Optimizations can trade correctness for speed if not measured carefully.",
    ],
    "documentation change": [
        "Documentation can drift from actual repo behavior if commands are not verified.",
    ],
    "release/deploy review": [
        "Release changes can impact production safety, rollout, and rollback readiness.",
    ],
    "unknown": [
        "The task is not clear enough to plan safely without clarification.",
    ],
}

TASK_TYPE_TESTS = {
    "project assessment": [
        "Verify which AI-ready project docs already exist and which are missing.",
        "Check that the suggested next task matches the current repo structure and risks.",
        "Avoid implementation until the assessment outcome is explicitly confirmed.",
    ],
    "feature": [
        "Cover the happy path for the new behavior.",
        "Add one error or empty-state test for the same flow.",
        "Run nearby regression tests for the touched area.",
    ],
    "bug fix": [
        "Reproduce the current failure before changing code.",
        "Add a regression test for the failing path.",
        "Run the closest affected smoke or unit tests.",
    ],
    "refactor": [
        "Run the closest existing tests before and after the refactor.",
        "Add a small regression test if behavior coverage is thin.",
    ],
    "test writing": [
        "Cover the main success path.",
        "Add one failure or empty-input case.",
    ],
    "database change": [
        "Validate migration or schema assumptions in a safe local path.",
        "Cover data read/write regression paths.",
        "Check permission or access-control cases if data is sensitive.",
    ],
    "UI change": [
        "Check success, loading, error, and empty states.",
        "Verify the flow on a small-screen layout if relevant.",
    ],
    "AI pipeline change": [
        "Cover fallback and timeout behavior.",
        "Test a safe failure path when the model or pipeline does not respond.",
        "Verify the expected output contract.",
    ],
    "security/privacy change": [
        "Add or run permission-boundary tests.",
        "Check negative cases for unauthorized access.",
        "Run regression tests around sensitive data handling.",
    ],
    "performance change": [
        "Compare before/after behavior on the slow path.",
        "Run regression tests to confirm correctness was preserved.",
    ],
    "documentation change": [
        "Verify that commands, paths, and examples still work.",
        "Check that the updated docs match current repo behavior.",
    ],
    "release/deploy review": [
        "Verify rollout and rollback steps against the current state.",
        "Check deployment configuration assumptions before release.",
    ],
    "unknown": [
        "Clarify the requested outcome before writing code or tests.",
    ],
}

TASK_TYPE_NEXT_ACTIONS = {
    "project assessment": "Inspect project docs, identify missing AI-ready docs, and propose the safest next coding task before implementation.",
    "feature": "Inspect the existing entrypoint and nearest product/architecture docs before defining the smallest user-visible change.",
    "bug fix": "Reproduce the bug and inspect the narrowest failing path before proposing a fix.",
    "refactor": "Identify the smallest behavior-preserving slice and inspect its current callers first.",
    "test writing": "Inspect existing tests around the target behavior and add the smallest missing coverage first.",
    "database change": "Inspect schema, query, and access-control assumptions before changing anything.",
    "UI change": "Inspect the current screen or component flow and list success, error, and empty states first.",
    "AI pipeline change": "Inspect the active pipeline, fallback path, and output contract before changing logic.",
    "security/privacy change": "Inspect permission boundaries and sensitive data paths before making any implementation decision.",
    "performance change": "Identify the specific slow path and verify what metric should improve before changing code.",
    "documentation change": "Inspect the source doc and verify the current repo behavior before editing text.",
    "release/deploy review": "Inspect deployment config, rollout steps, and rollback expectations before approval.",
    "unknown": "Clarify the task goal and affected area before planning implementation work.",
}

TOKEN_PATTERN = re.compile(r"[a-z0-9_/.-]+")


def _tokenize(task: str) -> set[str]:
    return set(TOKEN_PATTERN.findall(task.lower()))


def _normalize_project_docs(project_context: dict[str, object] | None) -> tuple[list[str], list[str]]:
    if project_context is None:
        return ["Project context was not provided."], ["Project context was not provided."]

    found_files = list(project_context.get("found_files", []))
    missing_files = list(project_context.get("missing_files", []))
    return found_files or ["none found"], missing_files or ["none"]


def _infer_domain_areas(task: str) -> list[str]:
    tokens = _tokenize(task)
    areas: list[str] = []

    def add(label: str) -> None:
        if label not in areas:
            areas.append(label)

    if {"telemetry", "logging", "log"} & tokens:
        add("telemetry or logging flow")
    if {"auth", "authentication", "authorization", "token", "permission"} & tokens:
        add("authentication and permission boundary")
    if {"database", "migration", "schema", "sql", "query", "table", "postgres", "supabase"} & tokens:
        add("database schema, migrations, and query layer")
    if {"ui", "screen", "component", "layout", "page", "button", "form"} & tokens:
        add("user interface component or route")
    if {"docs", "documentation", "readme", "guide"} & tokens:
        add("README and docs directory")
    if {"cli", "command", "argparse"} & tokens:
        add("CLI entrypoint and argument parsing")
    if {"config", "configuration", "env", "settings"} & tokens:
        add("configuration loading and environment handling")
    if {"test", "tests", "testing", "unittest", "smoke"} & tokens:
        add("existing test modules around the target behavior")
    if {"performance", "optimize", "latency", "cache", "slow", "faster"} & tokens:
        add("performance-critical path and repeated I/O")
    if {"ai", "model", "prompt", "inference", "embedding", "retrieval", "fallback"} & tokens:
        add("AI pipeline, prompt builder, or fallback path")

    return areas


def _prioritized_docs(found_docs: list[str]) -> list[str]:
    ordered_docs = [doc for doc in DOC_INSPECTION_PRIORITY if doc in found_docs]
    return ordered_docs[:2]


def _likely_inspection_targets(
    user_task: str, task_type: str, project_context: dict[str, object] | None
) -> list[str]:
    targets: list[str] = []
    found_docs = [] if project_context is None else list(project_context.get("found_files", []))

    for doc in _prioritized_docs(found_docs):
        if doc not in targets:
            targets.append(doc)

    task_targets = {
        "project assessment": [
            "project AI-ready docs and AGENTS.md",
            "repository entrypoints, structure, and current test surface",
            "safest next coding task based on current repo risks and missing docs",
        ],
        "feature": ["current entrypoint for the requested behavior", "nearby product or architecture boundary"],
        "bug fix": ["failing code path or command entrypoint", "existing regression tests for the failing flow"],
        "refactor": ["current implementation boundary", "callers of the code being simplified"],
        "test writing": ["current tests around the target behavior", "implementation path covered by the new tests"],
        "database change": ["schema definitions, migrations, and query layer", "data access or permission checks"],
        "UI change": ["screen, route, or component handling the flow", "state handling for loading and errors"],
        "AI pipeline change": ["active pipeline entrypoint", "fallback and output-contract path"],
        "security/privacy change": ["permission checks and auth boundary", "sensitive data handling path"],
        "performance change": ["slow path and repeated work", "caching or I/O boundary"],
        "documentation change": ["source document to update", "commands or examples referenced by the doc"],
        "release/deploy review": ["deployment config and rollout steps", "rollback and environment assumptions"],
        "unknown": [],
    }
    for target in task_targets.get(task_type, []):
        if target not in targets:
            targets.append(target)

    for area in _infer_domain_areas(user_task):
        if area not in targets:
            targets.append(area)

    return targets or ["unknown"]


def _build_risks(
    task_type: str,
    project_context: dict[str, object] | None,
    ai_brain_core_summary: dict[str, object] | None,
) -> list[str]:
    risks = list(TASK_TYPE_RISKS.get(task_type, TASK_TYPE_RISKS["unknown"]))

    if project_context is None:
        risks.append("Project-specific context was not provided.")
    else:
        missing_files = list(project_context.get("missing_files", []))
        if missing_files:
            risks.append(f"Project AI-ready files are incomplete: {', '.join(missing_files)}.")

    if ai_brain_core_summary is not None and ai_brain_core_summary.get("missing_count", 0):
        risks.append(
            "AI-Brain core guidance is incomplete locally; verify missing core notes before implementation."
        )

    return risks


def _build_summary(
    task_type: str,
    confidence: str,
    risk_level: str,
    project_context: dict[str, object] | None,
    ai_brain_core_summary: dict[str, object] | None,
) -> str:
    summary_parts = [f"{task_type} task", f"{confidence} confidence", f"{risk_level} risk"]
    if project_context is None:
        summary_parts.append("project context not provided")
    else:
        summary_parts.append(
            f"{len(project_context.get('found_files', []))} project docs found"
        )
    if ai_brain_core_summary is not None:
        summary_parts.append(
            f"{ai_brain_core_summary.get('found_count', 0)}/{ai_brain_core_summary.get('checked_count', 0)} AI-Brain core files available"
        )

    return "; ".join(summary_parts) + "."


def generate_planner_report(
    user_task: str,
    task_classification: dict[str, object],
    project_context: dict[str, object] | None = None,
    ai_brain_core_summary: dict[str, object] | None = None,
) -> dict[str, object]:
    task_type = str(task_classification.get("primary_task_type", "unknown"))
    confidence = str(task_classification.get("confidence", "low"))
    risk_level = str(task_classification.get("risk_level", "low"))
    found_docs, missing_files = _normalize_project_docs(project_context)
    summary = _build_summary(
        task_type, confidence, risk_level, project_context, ai_brain_core_summary
    )
    risks = _build_risks(task_type, project_context, ai_brain_core_summary)
    memory_sync_suggestion = suggest_memory_sync(
        user_task,
        task_classification,
        planner_summary=summary,
        findings_or_risks=risks,
    )
    
    knowledge_update_proposal = generate_knowledge_update_proposal(
        memory_sync_suggestion,
        user_task,
        findings=risks,
        suggested_tests=list(TASK_TYPE_TESTS.get(task_type, TASK_TYPE_TESTS["unknown"])),
    )

    return {
        "summary": summary,
        "task_type": task_type,
        "confidence": confidence,
        "risk_level": risk_level,
        "relevant_project_docs_found": found_docs,
        "missing_ai_ready_files": missing_files,
        "likely_files_or_areas_to_inspect": _likely_inspection_targets(
            user_task, task_type, project_context
        ),
        "risks": risks,
        "suggested_tests": list(TASK_TYPE_TESTS.get(task_type, TASK_TYPE_TESTS["unknown"])),
        "smallest_safe_next_action": TASK_TYPE_NEXT_ACTIONS.get(
            task_type, TASK_TYPE_NEXT_ACTIONS["unknown"]
        ),
        "approval_gate": evaluate_approval_requirements(
            task_classification=task_classification,
            requested_actions=["planner_report"],
        ),
        "knowledge_update_proposal": knowledge_update_proposal,
        "memory_docs_update_suggestion": memory_sync_suggestion, # kept for backward compatibility if needed
    }


def _format_section_value(value: object) -> str:
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return str(value)


def format_planner_report(report: dict[str, object]) -> str:
    ordered_sections = (
        ("Summary", report["summary"]),
        ("Task type", report["task_type"]),
        ("Confidence", report["confidence"]),
        ("Risk level", report["risk_level"]),
        ("Relevant project docs found", report["relevant_project_docs_found"]),
        ("Missing AI-ready files", report["missing_ai_ready_files"]),
        ("Likely files or areas to inspect", report["likely_files_or_areas_to_inspect"]),
        ("Risks", report["risks"]),
        ("Suggested tests", report["suggested_tests"]),
        ("Smallest safe next action", report["smallest_safe_next_action"]),
        ("Approval Gate", format_approval_gate_view(report["approval_gate"])),
        (
            "Knowledge Update Proposal",
            "\n"
            + format_knowledge_update_with_compatibility(
                report["knowledge_update_proposal"],
                report["memory_docs_update_suggestion"],
            ),
        ),
    )

    return "\n".join(f"{label}: {_format_section_value(value)}" for label, value in ordered_sections)
