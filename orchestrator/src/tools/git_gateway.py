from __future__ import annotations

from pathlib import Path
import subprocess

from core.approved_paths import ApprovedPathError, ensure_approved_path


class GitGatewayError(RuntimeError):
    """Raised when git state cannot be inspected safely."""


def resolve_project_path(project_path: str | Path) -> Path:
    resolved_path = Path(project_path).expanduser().resolve()
    if not resolved_path.exists():
        raise GitGatewayError(f"Project path does not exist: {resolved_path}")
    if not resolved_path.is_dir():
        raise GitGatewayError(f"Project path is not a directory: {resolved_path}")

    return resolved_path


def ensure_project_path_allowed(
    project_path: str | Path, approved_paths: list[str] | None = None
) -> Path:
    resolved_path = resolve_project_path(project_path)
    if approved_paths is None:
        return resolved_path

    try:
        return ensure_approved_path(resolved_path, approved_paths)
    except ApprovedPathError as exc:
        raise GitGatewayError(str(exc)) from exc


def _run_git_command(
    project_path: Path,
    args: list[str],
    allowed_exit_codes: tuple[int, ...] = (0,),
    timeout_seconds: int | None = None,
) -> subprocess.CompletedProcess[str]:
    command = ["git", "-C", str(project_path), *args]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            shell=False,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as exc:
        raise GitGatewayError("git command is not available on PATH.") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitGatewayError(f"Git command timed out: {' '.join(command)}") from exc

    if completed.returncode not in allowed_exit_codes:
        error_text = completed.stderr.strip() or completed.stdout.strip()
        raise GitGatewayError(error_text or f"Git command failed: {' '.join(command)}")

    return completed


def _is_git_repository(project_path: Path) -> bool:
    completed = _run_git_command(
        project_path,
        ["rev-parse", "--is-inside-work-tree"],
        allowed_exit_codes=(0, 128),
    )
    return completed.returncode == 0 and completed.stdout.strip() == "true"


def _parse_changed_files(status_output: str) -> list[str]:
    changed_files: list[str] = []
    for line in status_output.splitlines():
        if len(line) < 4:
            continue

        path_text = line[3:].strip()
        if " -> " in path_text:
            path_text = path_text.split(" -> ", 1)[1]
        changed_files.append(path_text)

    return changed_files


def _read_untracked_diffs(project_path: Path, status_output: str) -> str:
    diff_chunks: list[str] = []
    for line in status_output.splitlines():
        if not line.startswith("?? "):
            continue

        relative_path = line[3:].strip()
        completed = _run_git_command(
            project_path,
            ["diff", "--no-index", "--", "/dev/null", relative_path],
            allowed_exit_codes=(0, 1),
        )
        if completed.stdout.strip():
            diff_chunks.append(completed.stdout)

    return "".join(diff_chunks)


def inspect_git_state(
    project_path: str | Path,
    approved_paths: list[str] | None = None,
) -> dict[str, object]:
    resolved_project_path = ensure_project_path_allowed(project_path, approved_paths=approved_paths)
    if not _is_git_repository(resolved_project_path):
        return {
            "is_git_repo": False,
            "changed_files": [],
            "status_summary": "Not a git repository.",
            "diff_text": "",
            "diff_present": False,
        }

    status_completed = _run_git_command(
        resolved_project_path,
        ["status", "--porcelain"],
    )
    status_output = status_completed.stdout
    changed_files = _parse_changed_files(status_output)

    tracked_diff_completed = _run_git_command(
        resolved_project_path,
        ["diff", "--no-ext-diff"],
    )
    diff_text = tracked_diff_completed.stdout + _read_untracked_diffs(
        resolved_project_path,
        status_output,
    )

    if changed_files:
        status_summary = f"{len(changed_files)} changed file(s)."
    else:
        status_summary = "Working tree clean."

    return {
        "is_git_repo": True,
        "changed_files": changed_files,
        "status_summary": status_summary,
        "diff_text": diff_text,
        "diff_present": bool(diff_text.strip()),
    }


def inspect_git_log(
    project_path: str | Path,
    approved_paths: list[str] | None = None,
    *,
    max_entries: int = 20,
    timeout_seconds: int = 10,
) -> dict[str, object]:
    resolved_project_path = ensure_project_path_allowed(project_path, approved_paths=approved_paths)
    if not _is_git_repository(resolved_project_path):
        raise GitGatewayError("Not a git repository.")

    completed = _run_git_command(
        resolved_project_path,
        ["log", "--oneline", "-n", str(max_entries)],
        allowed_exit_codes=(0, 128),
        timeout_seconds=timeout_seconds,
    )

    if completed.returncode == 128:
        error_text = completed.stderr.strip() or completed.stdout.strip()
        if "does not have any commits yet" in error_text.lower():
            raise GitGatewayError("Git repository has no commits yet.")
        raise GitGatewayError(error_text or "git log could not be read safely.")

    log_text = completed.stdout.strip()
    if not log_text:
        raise GitGatewayError("Git repository has no commits yet.")

    lines = log_text.splitlines()
    return {
        "is_git_repo": True,
        "entry_count": len(lines),
        "log_text": log_text,
    }
