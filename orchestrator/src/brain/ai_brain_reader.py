from __future__ import annotations

from pathlib import Path


REQUIRED_CORE_FILES = {
    "core_rules": Path("CORE-RULES.md"),
    "readme_for_ai": Path("README-FOR-AI.md"),
    "priority_tiers": Path("02-Code") / "AI-Brain-Priority-Tiers.md",
    "context_budget_rules": Path("02-Code") / "Context-Budget-Rules.md",
}


class AIBrainReaderError(RuntimeError):
    """Raised when required AI-Brain files cannot be read safely."""


def _resolve_ai_brain_root(ai_brain_path: str | Path) -> Path:
    return Path(ai_brain_path).expanduser().resolve()


def resolve_ai_brain_relative_path(
    ai_brain_path: str | Path, relative_path: str | Path
) -> Path:
    root = _resolve_ai_brain_root(ai_brain_path)
    requested_path = Path(relative_path)
    if requested_path.is_absolute():
        raise AIBrainReaderError(f"AI-Brain path must be relative: {requested_path}")

    resolved_path = (root / requested_path).resolve()
    try:
        resolved_path.relative_to(root)
    except ValueError as exc:
        raise AIBrainReaderError(
            f"AI-Brain path escapes configured root: {requested_path}"
        ) from exc

    return resolved_path


def get_required_core_file_paths(ai_brain_path: str | Path) -> dict[str, Path]:
    return {
        name: resolve_ai_brain_relative_path(ai_brain_path, relative_path)
        for name, relative_path in REQUIRED_CORE_FILES.items()
    }


def inspect_required_core_files(ai_brain_path: str | Path) -> dict[str, object]:
    file_paths = get_required_core_file_paths(ai_brain_path)
    found = {name: path for name, path in file_paths.items() if path.is_file()}
    missing = {name: path for name, path in file_paths.items() if not path.is_file()}

    return {
        "checked_count": len(file_paths),
        "found_count": len(found),
        "missing_count": len(missing),
        "missing_files": missing,
    }


def read_required_core_files(ai_brain_path: str | Path) -> dict[str, str]:
    file_paths = get_required_core_file_paths(ai_brain_path)
    missing_files = [f"{name}: {path}" for name, path in file_paths.items() if not path.is_file()]
    if missing_files:
        missing_details = "\n".join(missing_files)
        raise AIBrainReaderError(f"Missing required AI-Brain core files:\n{missing_details}")

    return {name: path.read_text(encoding="utf-8") for name, path in file_paths.items()}


def read_note(ai_brain_path: str | Path, relative_path: str) -> str:
    note_path = resolve_ai_brain_relative_path(ai_brain_path, relative_path)
    if not note_path.is_file():
        raise AIBrainReaderError(f"AI-Brain note not found: {note_path}")

    return note_path.read_text(encoding="utf-8")
