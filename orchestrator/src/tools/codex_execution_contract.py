from __future__ import annotations

from pathlib import Path

from core.approved_paths import ApprovedPathError, ensure_approved_path
from core.safety import guard_text_output
from orchestration.approval_gate_manager import (
    evaluate_approval_requirements,
    format_approval_gate_view,
)
from orchestration.task_classifier import classify_task
from tools.codex_gateway import format_codex_prompt_package


MAX_TIMEOUT_SECONDS = 600
WILDCARD_TOKENS = ("*", "?", "[", "]")


def _build_safety_requirements() -> list[str]:
    return [
        "Project path must be inside approved paths.",
        "Allowed files must be provided, exist, and stay inside the approved project path.",
        "Directory targets and wildcard or broad file targets are not allowed.",
        "Explicit approval confirmation is required before any future Codex execution.",
        "Task text must pass secret and safety scanning.",
        "Codex prompt package content must pass secret and safety scanning.",
        "Timeout must be positive and no greater than 600 seconds.",
        "AI-Brain files are never valid allowed-file targets for execution.",
        "No execution is performed by this safety contract.",
    ]


def _blocked_summary(blocked_reasons: list[str]) -> str:
    return (
        f"Codex execution contract blocked due to {len(blocked_reasons)} issue(s). "
        "No execution was performed."
    )


def _resolve_project_path(
    project_path: str | Path,
    approved_paths: list[str] | tuple[str, ...] | None,
    blocked_reasons: list[str],
) -> Path | None:
    try:
        resolved_project_path = ensure_approved_path(project_path, approved_paths)
    except ApprovedPathError as exc:
        blocked_reasons.append(str(exc))
        return None

    if not resolved_project_path.exists():
        blocked_reasons.append(f"Project path does not exist: {resolved_project_path}")
        return None
    if not resolved_project_path.is_dir():
        blocked_reasons.append(f"Project path is not a directory: {resolved_project_path}")
        return None

    return resolved_project_path


def _resolve_allowed_file(project_root: Path, allowed_file: str) -> Path:
    requested_path = Path(allowed_file)
    if requested_path.is_absolute():
        return requested_path.expanduser().resolve()
    return (project_root / requested_path).resolve()


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


def evaluate_codex_execution_contract(
    project_path: str | Path,
    task_text: str,
    allowed_files: list[str] | tuple[str, ...],
    approved_paths: list[str] | tuple[str, ...] | None,
    approval_confirmed: bool,
    codex_prompt_package: dict[str, object] | str | None = None,
    timeout_seconds: int | None = None,
    ai_brain_path: str | Path | None = None,
) -> dict[str, object]:
    blocked_reasons: list[str] = []
    safety_requirements = _build_safety_requirements()
    approval_gate = evaluate_approval_requirements(
        task_classification=classify_task(task_text),
        requested_actions=["codex_execution"],
    )

    project_root = _resolve_project_path(project_path, approved_paths, blocked_reasons)
    resolved_allowed_files: list[str] = []
    resolved_ai_brain_root = None if ai_brain_path is None else Path(ai_brain_path).expanduser().resolve()

    if not allowed_files:
        blocked_reasons.append("At least one allowed file is required for Codex execution checks.")

    if project_root is not None:
        for allowed_file in allowed_files:
            if any(token in allowed_file for token in WILDCARD_TOKENS):
                blocked_reasons.append(f"Wildcard or broad allowed file is not allowed: {allowed_file}")
                continue

            resolved_target = _resolve_allowed_file(project_root, allowed_file)
            try:
                resolved_target.relative_to(project_root)
            except ValueError:
                blocked_reasons.append(
                    f"Allowed file is outside the approved project path: {resolved_target}"
                )
                continue

            try:
                ensure_approved_path(resolved_target, approved_paths)
            except ApprovedPathError as exc:
                blocked_reasons.append(str(exc))
                continue

            if resolved_ai_brain_root is not None:
                try:
                    resolved_target.relative_to(resolved_ai_brain_root)
                    blocked_reasons.append(f"Allowed file cannot point into AI-Brain: {resolved_target}")
                    continue
                except ValueError:
                    pass

            if not resolved_target.exists():
                blocked_reasons.append(f"Allowed file does not exist: {resolved_target}")
                continue
            if resolved_target.is_dir():
                blocked_reasons.append(f"Allowed file is a directory, not a file: {resolved_target}")
                continue

            resolved_allowed_files.append(str(resolved_target))

    if not approval_confirmed:
        blocked_reasons.append(
            "Explicit approval confirmation is required before any future Codex execution."
        )

    _append_guard_failures(blocked_reasons, task_text, "Codex execution task text")

    if codex_prompt_package is not None:
        if isinstance(codex_prompt_package, dict):
            prompt_text = format_codex_prompt_package(codex_prompt_package)
        else:
            prompt_text = str(codex_prompt_package)
        _append_guard_failures(blocked_reasons, prompt_text, "Codex execution prompt package")

    if timeout_seconds is not None:
        if timeout_seconds <= 0:
            blocked_reasons.append("Timeout must be greater than zero seconds.")
        elif timeout_seconds > MAX_TIMEOUT_SECONDS:
            blocked_reasons.append(
                f"Timeout exceeds the maximum allowed value of {MAX_TIMEOUT_SECONDS} seconds."
            )

    deduped_blocked_reasons: list[str] = []
    for reason in blocked_reasons:
        if reason not in deduped_blocked_reasons:
            deduped_blocked_reasons.append(reason)

    can_execute = not deduped_blocked_reasons
    execution_summary = (
        "All Codex execution safety requirements passed. No execution was performed."
        if can_execute
        else _blocked_summary(deduped_blocked_reasons)
    )

    return {
        "can_execute": can_execute,
        "approval_required": bool(approval_gate["approval_required"]),
        "risk_level": str(approval_gate["risk_level"]),
        "approval_gate": approval_gate,
        "blocked_reasons": deduped_blocked_reasons or ["none"],
        "allowed_files": resolved_allowed_files or ["none"],
        "safety_requirements": safety_requirements,
        "execution_summary": execution_summary,
    }


def format_codex_execution_contract_view(result: dict[str, object]) -> str:
    blocked_reasons = list(result.get("blocked_reasons", [])) or ["none"]
    allowed_files = list(result.get("allowed_files", [])) or ["none"]
    safety_requirements = list(result.get("safety_requirements", [])) or ["none"]
    approval_gate = result.get("approval_gate")
    if isinstance(approval_gate, dict):
        approval_gate_view = format_approval_gate_view(approval_gate)
    else:
        approval_gate_view = format_approval_gate_view(
            {
                "approval_required": result.get("approval_required", False),
                "risk_level": result.get("risk_level", "low"),
                "reasons": [],
                "blocked_actions": [],
                "recommended_user_confirmation": "",
            }
        )

    return "\n".join(
        [
            f"Can execute: {'yes' if result.get('can_execute') else 'no'}",
            "Approval gate:",
            approval_gate_view,
            f"Blocked reasons: {'; '.join(str(item) for item in blocked_reasons)}",
            f"Allowed files: {'; '.join(str(item) for item in allowed_files)}",
            f"Safety requirements: {'; '.join(str(item) for item in safety_requirements)}",
            f"Execution summary: {result.get('execution_summary', '')}",
        ]
    )


def format_codex_execution_contract(result: dict[str, object]) -> str:
    return format_codex_execution_contract_view(result)
