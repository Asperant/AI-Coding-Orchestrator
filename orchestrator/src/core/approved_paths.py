from __future__ import annotations

from pathlib import Path


class ApprovedPathError(RuntimeError):
    """Raised when a target path is not allowed by approved path policy."""


def _resolve_path(path_value: str | Path) -> Path:
    return Path(path_value).expanduser().resolve()


def ensure_approved_path(
    target_path: str | Path,
    approved_paths: list[str] | tuple[str, ...] | None,
) -> Path:
    if approved_paths is None:
        raise ApprovedPathError("Approved paths are missing from configuration.")
    if not isinstance(approved_paths, (list, tuple)):
        raise ApprovedPathError("Approved paths must be a list or tuple.")
    if not approved_paths:
        raise ApprovedPathError("Approved paths are empty.")

    resolved_target_path = _resolve_path(target_path)
    resolved_approved_paths: list[Path] = []
    for approved_path in approved_paths:
        if not isinstance(approved_path, (str, Path)):
            raise ApprovedPathError("Approved paths must contain only path strings.")
        resolved_approved_paths.append(_resolve_path(approved_path))

    for approved_root in resolved_approved_paths:
        try:
            resolved_target_path.relative_to(approved_root)
            return resolved_target_path
        except ValueError:
            continue

    raise ApprovedPathError(
        f"Target path is outside approved paths: {resolved_target_path}"
    )
