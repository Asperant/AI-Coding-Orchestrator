from __future__ import annotations

from pathlib import Path


EXPECTED_PROJECT_CONTEXT_FILES = (
    Path("AGENTS.md"),
    Path("docs") / "product-context.md",
    Path("docs") / "architecture.md",
    Path("docs") / "project-map.md",
    Path("docs") / "quality-gates.md",
    Path("docs") / "risk-registry.md",
    Path("docs") / "test-scenarios.md",
)


class ProjectContextReaderError(RuntimeError):
    """Raised when project context files cannot be inspected safely."""


def resolve_working_directory(working_directory: str | Path) -> Path:
    resolved_path = Path(working_directory).expanduser().resolve()
    if not resolved_path.exists():
        raise ProjectContextReaderError(f"Working directory does not exist: {resolved_path}")
    if not resolved_path.is_dir():
        raise ProjectContextReaderError(f"Working directory is not a directory: {resolved_path}")

    return resolved_path


def inspect_project_context(working_directory: str | Path) -> dict[str, object]:
    root = resolve_working_directory(working_directory)
    found_files: list[str] = []
    missing_files: list[str] = []

    for relative_path in EXPECTED_PROJECT_CONTEXT_FILES:
        relative_path_text = relative_path.as_posix()
        if (root / relative_path).is_file():
            found_files.append(relative_path_text)
        else:
            missing_files.append(relative_path_text)

    return {
        "working_directory": str(root),
        "found_files": found_files,
        "missing_files": missing_files,
        "project_docs_count": len(found_files),
    }
