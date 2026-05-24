from __future__ import annotations

from pathlib import Path

from core.approved_paths import ApprovedPathError, ensure_approved_path
from orchestration.approval_gate_manager import (
    evaluate_approval_requirements,
    format_approval_gate_view,
)

WILDCARD_TOKENS = ("*", "?", "[", "]")


class EditPlanError(RuntimeError):
    """Raised when an edit plan cannot be evaluated safely."""


def _resolve_project_path(
    project_path: str | Path,
    approved_paths: list[str] | tuple[str, ...] | None,
) -> Path:
    try:
        resolved_project_path = ensure_approved_path(project_path, approved_paths)
    except ApprovedPathError as exc:
        raise EditPlanError(str(exc)) from exc

    if not resolved_project_path.exists():
        raise EditPlanError(f"Project path does not exist: {resolved_project_path}")
    if not resolved_project_path.is_dir():
        raise EditPlanError(f"Project path is not a directory: {resolved_project_path}")

    return resolved_project_path


def _resolve_target_path(project_root: Path, requested_path: str) -> Path:
    requested = Path(requested_path)
    if requested.is_absolute():
        return requested.expanduser().resolve()
    return (project_root / requested).resolve()


def _build_blocked_item(path: str, reason: str) -> dict[str, str]:
    return {"path": path, "reason": reason}


def generate_edit_plan(
    project_path: str | Path,
    task_text: str,
    requested_files: list[str] | tuple[str, ...],
    approved_paths: list[str] | tuple[str, ...] | None,
    task_classification: dict[str, object] | None = None,
) -> dict[str, object]:
    del task_text

    project_root = _resolve_project_path(project_path, approved_paths)
    approval_gate = evaluate_approval_requirements(
        task_classification=task_classification,
        requested_actions=["file_edit"],
    )

    target_files: list[str] = []
    blocked_files: list[dict[str, str]] = []
    risks = list(approval_gate["reasons"])

    if not requested_files:
        blocked_files.append(
            _build_blocked_item("(none)", "No target files were provided for the edit dry run.")
        )

    for requested_file in requested_files:
        if any(token in requested_file for token in WILDCARD_TOKENS):
            blocked_files.append(
                _build_blocked_item(requested_file, "Wildcard or broad edit targets are not allowed.")
            )
            continue

        resolved_target = _resolve_target_path(project_root, requested_file)
        try:
            resolved_target.relative_to(project_root)
        except ValueError:
            blocked_files.append(
                _build_blocked_item(
                    requested_file,
                    f"Target file is outside the approved project path: {resolved_target}",
                )
            )
            continue

        try:
            ensure_approved_path(resolved_target, approved_paths)
        except ApprovedPathError as exc:
            blocked_files.append(_build_blocked_item(requested_file, str(exc)))
            continue

        if not resolved_target.exists():
            blocked_files.append(
                _build_blocked_item(
                    requested_file,
                    f"Target file does not exist: {resolved_target}",
                )
            )
            continue

        if resolved_target.is_dir():
            blocked_files.append(
                _build_blocked_item(
                    requested_file,
                    f"Target path is a directory, not a file: {resolved_target}",
                )
            )
            continue

        target_files.append(str(resolved_target))

    for blocked_file in blocked_files:
        if blocked_file["reason"] not in risks:
            risks.append(blocked_file["reason"])

    if "Dry run only: edit mode is not enabled in read-only mode." not in risks:
        risks.append("Dry run only: edit mode is not enabled in read-only mode.")

    return {
        "dry_run": True,
        "edit_allowed_now": False,
        "approval_required": approval_gate["approval_required"],
        "project_path": str(project_root),
        "target_files": target_files or ["none"],
        "blocked_files": blocked_files or [{"path": "none", "reason": "none"}],
        "risks": risks,
        "next_required_confirmation": approval_gate["recommended_user_confirmation"],
        "approval_gate": approval_gate,
    }


def format_edit_plan(edit_plan: dict[str, object]) -> str:
    blocked_items = list(edit_plan.get("blocked_files", []))
    blocked_summary = "; ".join(
        f"{item['path']} ({item['reason']})" for item in blocked_items
    )

    lines = [
        f"Dry run: {'yes' if edit_plan.get('dry_run') else 'no'}",
        f"Edit allowed now: {'yes' if edit_plan.get('edit_allowed_now') else 'no'}",
        f"Approval required: {'yes' if edit_plan.get('approval_required') else 'no'}",
        f"Project path: {edit_plan.get('project_path', '')}",
        f"Target files: {'; '.join(edit_plan.get('target_files', []))}",
        f"Blocked files: {blocked_summary}",
        f"Risks: {'; '.join(edit_plan.get('risks', []))}",
        "Approval Gate: "
        f"{format_approval_gate_view(edit_plan.get('approval_gate', {}))}",
        "Next required confirmation: "
        f"{edit_plan.get('next_required_confirmation', '')}",
    ]
    return "\n".join(lines)
