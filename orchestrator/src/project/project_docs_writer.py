from __future__ import annotations

from pathlib import Path

from core.approved_paths import ApprovedPathError, ensure_approved_path
from core.safety import guard_text_output


class ProjectDocsWriterError(RuntimeError):
    """Raised when a project docs write cannot be completed safely."""


def _blocked_result(target_path: str, message: str) -> dict[str, object]:
    return {
        "written": False,
        "target_path": target_path,
        "action": "blocked",
        "message": message,
    }


def _resolve_project_path(
    project_path: str | Path,
    approved_paths: list[str] | tuple[str, ...] | None,
) -> Path:
    try:
        resolved_project_path = ensure_approved_path(project_path, approved_paths)
    except ApprovedPathError as exc:
        raise ProjectDocsWriterError(str(exc)) from exc

    if not resolved_project_path.exists():
        raise ProjectDocsWriterError(f"Project path does not exist: {resolved_project_path}")
    if not resolved_project_path.is_dir():
        raise ProjectDocsWriterError(f"Project path is not a directory: {resolved_project_path}")

    return resolved_project_path


def _resolve_target_path(project_root: Path, relative_docs_path: str) -> Path:
    relative_path = Path(relative_docs_path)
    if relative_path.is_absolute():
        raise ProjectDocsWriterError("Project docs path must be relative to the project root.")

    resolved_docs_root = (project_root / "docs").resolve()
    resolved_target_path = (project_root / relative_path).resolve()

    try:
        resolved_target_path.relative_to(resolved_docs_root)
    except ValueError as exc:
        raise ProjectDocsWriterError(
            f"Project docs path must stay under project docs/: {resolved_target_path}"
        ) from exc

    if resolved_target_path == resolved_docs_root:
        raise ProjectDocsWriterError("Project docs target must be a file inside docs/, not the docs directory.")

    return resolved_target_path


def write_project_doc(
    project_path: str | Path,
    relative_docs_path: str,
    content: str,
    approved_paths: list[str] | tuple[str, ...] | None,
    approval_confirmed: bool,
    mode: str = "create",
) -> dict[str, object]:
    project_root = _resolve_project_path(project_path, approved_paths)
    resolved_target_path = _resolve_target_path(project_root, relative_docs_path)

    try:
        ensure_approved_path(resolved_target_path, approved_paths)
    except ApprovedPathError as exc:
        raise ProjectDocsWriterError(str(exc)) from exc

    if mode not in {"create", "append"}:
        raise ProjectDocsWriterError(f"Unsupported project docs write mode: {mode}")

    if not approval_confirmed:
        return _blocked_result(
            str(resolved_target_path),
            "Project docs write requires explicit approval confirmation.",
        )

    content_guard_result = guard_text_output(content, "Project docs write")
    if not content_guard_result["allowed"]:
        return _blocked_result(
            str(resolved_target_path),
            str(content_guard_result["safe_message"]),
        )

    if resolved_target_path.exists() and resolved_target_path.is_dir():
        return _blocked_result(
            str(resolved_target_path),
            f"Project docs target is a directory, not a file: {resolved_target_path}",
        )

    resolved_target_path.parent.mkdir(parents=True, exist_ok=True)

    if mode == "create":
        if resolved_target_path.exists():
            return _blocked_result(
                str(resolved_target_path),
                f"Create mode will not overwrite an existing file: {resolved_target_path}",
            )
        resolved_target_path.write_text(content, encoding="utf-8")
        return {
            "written": True,
            "target_path": str(resolved_target_path),
            "action": "create",
            "message": f"Project docs file created: {resolved_target_path}",
        }

    if resolved_target_path.exists():
        existing_content = resolved_target_path.read_text(encoding="utf-8")
        separator = "" if not existing_content or existing_content.endswith("\n") else "\n"
        resolved_target_path.write_text(
            f"{existing_content}{separator}{content}",
            encoding="utf-8",
        )
        return {
            "written": True,
            "target_path": str(resolved_target_path),
            "action": "append",
            "message": f"Project docs file appended: {resolved_target_path}",
        }

    resolved_target_path.write_text(content, encoding="utf-8")
    return {
        "written": True,
        "target_path": str(resolved_target_path),
        "action": "append",
        "message": f"Project docs file created by append mode: {resolved_target_path}",
    }
