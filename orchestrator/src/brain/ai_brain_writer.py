from __future__ import annotations

from pathlib import Path
import re

from core.safety import guard_text_output


SAFE_NAME_RE = re.compile(r"[^a-z0-9._-]+")
BLOCKED_ROOT_FILES = {
    Path("CORE-RULES.md"),
    Path("README-FOR-AI.md"),
    Path("Home.md"),
}


class AIBrainWriterError(RuntimeError):
    """Raised when an AI-Brain write cannot be completed safely."""


def _blocked_result(target_path: str, message: str) -> dict[str, object]:
    return {
        "written": False,
        "target_path": target_path,
        "action": "blocked",
        "message": message,
    }


def _resolve_ai_brain_root(ai_brain_path: str | Path) -> Path:
    resolved_root = Path(ai_brain_path).expanduser().resolve()
    if not resolved_root.exists():
        raise AIBrainWriterError(f"AI-Brain path does not exist: {resolved_root}")
    if not resolved_root.is_dir():
        raise AIBrainWriterError(f"AI-Brain path is not a directory: {resolved_root}")
    return resolved_root


def _sanitize_filename(source_text: str, fallback: str) -> str:
    first_line = next((line.strip() for line in source_text.splitlines() if line.strip()), fallback)
    sanitized = SAFE_NAME_RE.sub("-", first_line.lower()).strip("._-")
    if not sanitized:
        sanitized = fallback
    return f"{sanitized}.md" if not sanitized.endswith(".md") else sanitized


def _resolve_target_path(
    ai_brain_root: Path,
    memory_type: str,
    relative_path: str | None,
    content: str,
) -> Path:
    if memory_type == "lesson":
        target_relative = Path("02-Code") / "Lessons-Learned.md"
    elif memory_type == "decision":
        target_relative = Path("06-Decisions") / (
            relative_path if relative_path else _sanitize_filename(content, "decision-entry")
        )
    elif memory_type in {"example", "bugfix"}:
        target_relative = Path("07-Examples") / (
            relative_path if relative_path else _sanitize_filename(content, f"{memory_type}-entry")
        )
    else:
        raise AIBrainWriterError(f"Unsupported AI-Brain memory type: {memory_type}")

    relative_candidate = Path(target_relative)
    if relative_candidate.is_absolute():
        raise AIBrainWriterError("AI-Brain target path must be relative.")

    resolved_target = (ai_brain_root / relative_candidate).resolve()
    try:
        relative_resolved = resolved_target.relative_to(ai_brain_root)
    except ValueError as exc:
        raise AIBrainWriterError(
            f"AI-Brain write target escapes configured root: {relative_candidate}"
        ) from exc

    if relative_resolved in BLOCKED_ROOT_FILES:
        raise AIBrainWriterError(f"AI-Brain write target is blocked: {relative_resolved}")
    if relative_resolved.parts and relative_resolved.parts[0] == "05-Agents":
        raise AIBrainWriterError(f"AI-Brain write target is blocked: {relative_resolved}")

    if memory_type == "lesson" and relative_resolved != Path("02-Code") / "Lessons-Learned.md":
        raise AIBrainWriterError("Lesson writes are allowed only in 02-Code/Lessons-Learned.md.")
    if memory_type == "decision":
        try:
            relative_resolved.relative_to(Path("06-Decisions"))
        except ValueError as exc:
            raise AIBrainWriterError("Decision writes must stay under 06-Decisions/.") from exc
    if memory_type in {"example", "bugfix"}:
        try:
            relative_resolved.relative_to(Path("07-Examples"))
        except ValueError as exc:
            raise AIBrainWriterError(f"{memory_type} writes must stay under 07-Examples/.") from exc

    return resolved_target


def write_ai_brain_memory(
    ai_brain_path: str | Path,
    memory_type: str,
    relative_path: str | None,
    content: str,
    approval_confirmed: bool,
    mode: str = "create",
) -> dict[str, object]:
    ai_brain_root = _resolve_ai_brain_root(ai_brain_path)
    resolved_target = _resolve_target_path(ai_brain_root, memory_type, relative_path, content)

    if mode not in {"create", "append"}:
        raise AIBrainWriterError(f"Unsupported AI-Brain write mode: {mode}")
    if memory_type != "lesson" and mode == "append":
        raise AIBrainWriterError("Append mode is allowed only for lesson writes.")

    if not approval_confirmed:
        return _blocked_result(
            str(resolved_target),
            "AI-Brain write requires explicit approval confirmation.",
        )

    content_guard_result = guard_text_output(content, "AI-Brain write")
    if not content_guard_result["allowed"]:
        return _blocked_result(
            str(resolved_target),
            str(content_guard_result["safe_message"]),
        )

    if resolved_target.exists() and resolved_target.is_dir():
        return _blocked_result(
            str(resolved_target),
            f"AI-Brain target is a directory, not a file: {resolved_target}",
        )

    resolved_target.parent.mkdir(parents=True, exist_ok=True)

    if mode == "create":
        if resolved_target.exists():
            return _blocked_result(
                str(resolved_target),
                f"Create mode will not overwrite an existing AI-Brain file: {resolved_target}",
            )
        resolved_target.write_text(content, encoding="utf-8")
        return {
            "written": True,
            "target_path": str(resolved_target),
            "action": "create",
            "message": f"AI-Brain memory file created: {resolved_target}",
        }

    existing_content = "" if not resolved_target.exists() else resolved_target.read_text(encoding="utf-8")
    separator = "" if not existing_content or existing_content.endswith("\n") else "\n"
    resolved_target.write_text(f"{existing_content}{separator}{content}", encoding="utf-8")
    return {
        "written": True,
        "target_path": str(resolved_target),
        "action": "append",
        "message": f"AI-Brain memory file appended: {resolved_target}",
    }
