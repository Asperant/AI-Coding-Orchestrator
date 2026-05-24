from __future__ import annotations

from pathlib import Path

from core.approved_paths import ApprovedPathError, ensure_approved_path


class FilesystemGatewayError(RuntimeError):
    """Raised when a filesystem gateway operation is not allowed."""


def read_file(
    path: str | Path,
    approved_paths: list[str] | tuple[str, ...] | None,
) -> str:
    try:
        resolved_path = ensure_approved_path(path, approved_paths)
    except ApprovedPathError as exc:
        raise FilesystemGatewayError(str(exc)) from exc

    if not resolved_path.exists():
        raise FilesystemGatewayError(f"File does not exist: {resolved_path}")
    if resolved_path.is_dir():
        raise FilesystemGatewayError(f"Expected a file but received a directory: {resolved_path}")

    return resolved_path.read_text(encoding="utf-8", errors="replace")


def write_file(
    path: str | Path,
    content: str,
    approved_paths: list[str] | tuple[str, ...] | None,
) -> None:
    del path
    del content
    del approved_paths
    raise FilesystemGatewayError(
        "Write operations require explicit approval and are blocked in read-only mode."
    )
