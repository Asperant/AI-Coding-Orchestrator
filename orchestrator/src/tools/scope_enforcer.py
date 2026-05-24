from __future__ import annotations

from pathlib import Path


def _resolve_inside_project(project_root: Path, file_path: str) -> tuple[str | None, str | None]:
    raw_path = str(file_path or "").strip()
    if not raw_path:
        return None, "Unknown changed file entry could not be verified safely."

    candidate = Path(raw_path)
    if candidate.is_absolute():
        resolved = candidate.expanduser().resolve()
    else:
        resolved = (project_root / candidate).resolve()

    try:
        resolved.relative_to(project_root)
    except ValueError:
        return None, f"Path is outside the approved project scope: {raw_path}"

    return str(resolved), None


def enforce_changed_file_scope(
    project_path: str | Path,
    allowed_files: list[str] | tuple[str, ...],
    changed_files: list[str] | tuple[str, ...],
) -> dict[str, object]:
    project_root = Path(project_path).expanduser().resolve()

    normalized_allowed_files: list[str] = []
    normalized_changed_files: list[str] = []
    violations: list[str] = []

    for file_path in list(allowed_files):
        resolved_path, violation = _resolve_inside_project(project_root, str(file_path))
        if violation is not None:
            violations.append(f"Allowed file validation failed: {violation}")
            continue
        if resolved_path not in normalized_allowed_files:
            normalized_allowed_files.append(resolved_path)

    for file_path in list(changed_files):
        resolved_path, violation = _resolve_inside_project(project_root, str(file_path))
        if violation is not None:
            violations.append(f"Changed file validation failed: {violation}")
            continue
        normalized_changed_files.append(resolved_path)
        if resolved_path not in normalized_allowed_files:
            violations.append(f"Changed file is outside the explicitly allowed scope: {resolved_path}")

    passed = not violations
    if passed:
        message = "All changed files stayed within the explicitly allowed scope."
    else:
        message = "Scope enforcement detected changes outside the explicitly allowed files."

    return {
        "passed": passed,
        "violations": violations or ["none"],
        "allowed_files": normalized_allowed_files,
        "changed_files": normalized_changed_files or ["none"],
        "message": message,
    }


def format_scope_enforcement_result(result: dict[str, object]) -> str:
    return "\n".join(
        [
            f"Passed: {'yes' if result.get('passed') else 'no'}",
            f"Allowed files: {', '.join(result.get('allowed_files', [])) or 'none'}",
            f"Changed files: {', '.join(result.get('changed_files', [])) or 'none'}",
            f"Violations: {'; '.join(result.get('violations', []))}",
            f"Message: {result.get('message', '')}",
        ]
    )
