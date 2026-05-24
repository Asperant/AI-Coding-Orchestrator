from __future__ import annotations

import shlex
import subprocess
import os
from pathlib import Path

from core.approved_paths import ApprovedPathError, ensure_approved_path


DEFAULT_TEST_TIMEOUT_SECONDS = 120
MAX_TEST_TIMEOUT_SECONDS = 600
_UNSAFE_SHELL_TOKENS = ("&&", "||", ";", "|", ">", ">>", "<", "`", "$(", "rm", "sudo", "curl", "wget")
_ALLOWED_TEST_COMMANDS: tuple[tuple[str, ...], ...] = (
    ("python", "-m", "unittest"),
    ("python", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"),
    ("pytest",),
    ("npm", "test"),
    ("npm", "run", "test"),
)


def _normalize_test_command(
    test_command: str | list[str] | tuple[str, ...],
) -> list[str]:
    if isinstance(test_command, str):
        command = shlex.split(test_command)
    else:
        command = [str(item) for item in test_command]
    return [item for item in command if item]


def _contains_unsafe_shell_syntax(tokens: list[str]) -> bool:
    for token in tokens:
        if token in _UNSAFE_SHELL_TOKENS:
            return True
        if any(marker in token for marker in ("&&", "||", ";", "|", ">", "<", "`", "$(")):
            return True
    return False


def run_test_command(
    project_path: str | Path,
    test_command: str | list[str] | tuple[str, ...],
    approved_paths: list[str] | tuple[str, ...] | None,
    timeout_seconds: int = DEFAULT_TEST_TIMEOUT_SECONDS,
) -> dict[str, object]:
    normalized_command = _normalize_test_command(test_command)

    env = None
    command_to_check = normalized_command
    if normalized_command and normalized_command[0] == "PYTHONDONTWRITEBYTECODE=1":
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        command_to_check = normalized_command[1:]

    if not command_to_check:
        return {
            "ran": False,
            "blocked": True,
            "passed": False,
            "return_code": None,
            "timed_out": False,
            "stdout": "",
            "stderr": "",
            "message": "Test command is required.",
        }

    if _contains_unsafe_shell_syntax(normalized_command):
        return {
            "ran": False,
            "blocked": True,
            "passed": False,
            "return_code": None,
            "timed_out": False,
            "stdout": "",
            "stderr": "",
            "message": "Unsafe shell syntax is not allowed in test commands.",
        }

    if tuple(command_to_check) not in _ALLOWED_TEST_COMMANDS:
        return {
            "ran": False,
            "blocked": True,
            "passed": False,
            "return_code": None,
            "timed_out": False,
            "stdout": "",
            "stderr": "",
            "message": "Test command is not in the safe allowlist.",
        }

    if timeout_seconds <= 0:
        return {
            "ran": False,
            "blocked": True,
            "passed": False,
            "return_code": None,
            "timed_out": False,
            "stdout": "",
            "stderr": "",
            "message": "Test timeout must be greater than zero.",
        }

    if timeout_seconds > MAX_TEST_TIMEOUT_SECONDS:
        return {
            "ran": False,
            "blocked": True,
            "passed": False,
            "return_code": None,
            "timed_out": False,
            "stdout": "",
            "stderr": "",
            "message": f"Test timeout must be {MAX_TEST_TIMEOUT_SECONDS} seconds or less.",
        }

    try:
        approved_project_path = ensure_approved_path(project_path, approved_paths)
    except ApprovedPathError as exc:
        return {
            "ran": False,
            "blocked": True,
            "passed": False,
            "return_code": None,
            "timed_out": False,
            "stdout": "",
            "stderr": "",
            "message": str(exc),
        }
    resolved_project_path = Path(approved_project_path).resolve()

    try:
        completed = subprocess.run(
            command_to_check,
            cwd=resolved_project_path,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "ran": True,
            "blocked": False,
            "passed": False,
            "return_code": None,
            "timed_out": True,
            "stdout": exc.output or "",
            "stderr": exc.stderr or "",
            "message": f"Test command timed out after {timeout_seconds} seconds.",
        }
    except FileNotFoundError:
        return {
            "ran": False,
            "blocked": False,
            "passed": False,
            "return_code": None,
            "timed_out": False,
            "stdout": "",
            "stderr": "",
            "message": f"Test command was not found on PATH: {normalized_command[0]}",
        }

    passed = completed.returncode == 0
    return {
        "ran": True,
        "blocked": False,
        "passed": passed,
        "return_code": completed.returncode,
        "timed_out": False,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "message": (
            "Test command completed successfully."
            if passed
            else f"Test command exited with return code {completed.returncode}."
        ),
    }


def format_test_result(result: dict[str, object]) -> str:
    return "\n".join(
        [
            f"Ran: {'yes' if result.get('ran') else 'no'}",
            f"Blocked: {'yes' if result.get('blocked') else 'no'}",
            f"Passed: {'yes' if result.get('passed') else 'no'}",
            f"Return code: {result.get('return_code') if result.get('return_code') is not None else 'none'}",
            f"Timed out: {'yes' if result.get('timed_out') else 'no'}",
            f"Message: {result.get('message', '')}",
            f"Stdout: {result.get('stdout') or 'none'}",
            f"Stderr: {result.get('stderr') or 'none'}",
        ]
    )
