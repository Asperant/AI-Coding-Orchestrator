from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from core.safety import guard_text_output
from orchestration.multi_agent_review import (
    format_multi_agent_diff_review,
    generate_multi_agent_diff_review,
    generate_secret_blocked_diff_review,
)
from tools.codex_execution_contract import (
    evaluate_codex_execution_contract,
    format_codex_execution_contract_view,
)
from tools.git_gateway import inspect_git_state


def _blocked_result(
    contract: dict[str, object],
    message: str,
) -> dict[str, object]:
    return {
        "executed": False,
        "blocked": True,
        "return_code": None,
        "timed_out": False,
        "stdout": "",
        "stderr": "",
        "contract": contract,
        "message": message,
    }


def _normalize_stream_value(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def execute_codex_task(
    project_path: str | Path,
    task_text: str,
    allowed_files: list[str] | tuple[str, ...],
    approved_paths: list[str] | tuple[str, ...] | None,
    approval_confirmed: bool,
    prompt_package_text: str,
    timeout_seconds: int = 300,
    execute_confirmed: bool = False,
    codex_command: str = "codex",
    ai_brain_path: str | Path | None = None,
) -> dict[str, object]:
    contract = evaluate_codex_execution_contract(
        project_path,
        task_text,
        allowed_files,
        approved_paths,
        approval_confirmed,
        codex_prompt_package=prompt_package_text,
        timeout_seconds=timeout_seconds,
        ai_brain_path=ai_brain_path,
    )

    if not contract["can_execute"]:
        return _blocked_result(
            contract,
            "Codex execution is blocked because the safety contract did not pass.",
        )

    if not execute_confirmed:
        return _blocked_result(
            contract,
            "Codex execution confirmation is required before any execution can run.",
        )

    if not prompt_package_text.strip():
        return _blocked_result(
            contract,
            "Codex execution requires a non-empty prompt package text.",
        )

    if not codex_command.strip():
        return _blocked_result(
            contract,
            "Codex command name is required before execution can run.",
        )

    resolved_command = shutil.which(codex_command)
    if resolved_command is None:
        return _blocked_result(
            contract,
            f"Codex command was not found on PATH: {codex_command}",
        )

    resolved_project_path = Path(project_path).expanduser().resolve()

    try:
        completed = subprocess.run(
            [
                resolved_command,
                "exec",
                "-",
                "--cd",
                str(resolved_project_path),
                "--sandbox",
                "workspace-write",
                "--ephemeral",
            ],
            input=prompt_package_text,
            text=True,
            capture_output=True,
            cwd=resolved_project_path,
            timeout=timeout_seconds,
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "executed": True,
            "blocked": False,
            "return_code": None,
            "timed_out": True,
            "stdout": _normalize_stream_value(exc.output),
            "stderr": _normalize_stream_value(exc.stderr),
            "contract": contract,
            "message": (
                f"Codex command timed out after {timeout_seconds} seconds."
            ),
        }

    message = (
        "Codex command completed successfully."
        if completed.returncode == 0
        else f"Codex command exited with return code {completed.returncode}."
    )

    return {
        "executed": True,
        "blocked": False,
        "return_code": completed.returncode,
        "timed_out": False,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "contract": contract,
        "message": message,
    }


def execute_codex_task_with_post_review(
    project_path: str | Path,
    task_text: str,
    allowed_files: list[str] | tuple[str, ...],
    approved_paths: list[str] | tuple[str, ...] | None,
    approval_confirmed: bool,
    prompt_package_text: str,
    timeout_seconds: int = 300,
    execute_confirmed: bool = False,
    codex_command: str = "codex",
    ai_brain_path: str | Path | None = None,
    post_codex_review: bool = False,
    task_classification: dict[str, object] | None = None,
    project_context: dict[str, object] | None = None,
) -> dict[str, object]:
    result = execute_codex_task(
        project_path,
        task_text,
        allowed_files,
        approved_paths,
        approval_confirmed,
        prompt_package_text,
        timeout_seconds=timeout_seconds,
        execute_confirmed=execute_confirmed,
        codex_command=codex_command,
        ai_brain_path=ai_brain_path,
    )

    result["post_review_ran"] = False
    result["post_review_decision"] = "not run"
    result["post_review_report"] = ""
    result["post_review_message"] = "Post-Codex review was not requested."
    result["post_review_should_block_save"] = False
    result["post_review_changed_files"] = []
    result["post_review_is_git_repo"] = False

    if not post_codex_review:
        return result

    if result["blocked"] or not result["executed"] or result["timed_out"] or result["return_code"] != 0:
        result["post_review_message"] = (
            "Post-Codex review did not run because Codex execution did not complete successfully."
        )
        return result

    git_state = inspect_git_state(project_path, approved_paths=list(approved_paths or []))
    review_guard_result = None
    if git_state["diff_present"]:
        review_guard_result = guard_text_output(
            str(git_state["diff_text"]),
            "Post-Codex diff review output",
        )

    if review_guard_result is not None and not review_guard_result["allowed"]:
        review_report = generate_secret_blocked_diff_review(
            git_state,
            review_guard_result,
            task_classification,
        )
        result["post_review_should_block_save"] = bool(review_guard_result["should_block_save"])
    else:
        review_report = generate_multi_agent_diff_review(
            git_state,
            task_classification=task_classification,
            project_context=project_context,
        )

    result["post_review_ran"] = True
    result["post_review_decision"] = str(review_report["decision"])
    result["post_review_report"] = format_multi_agent_diff_review(review_report)
    result["post_review_changed_files"] = list(git_state.get("changed_files", []))
    result["post_review_is_git_repo"] = bool(git_state.get("is_git_repo"))
    if not git_state["is_git_repo"]:
        result["post_review_message"] = "Post-Codex review could not inspect a diff because the project is not a git repository."
    else:
        result["post_review_message"] = "Post-Codex diff review completed."
    return result


def format_codex_execution_result(result: dict[str, object]) -> str:
    contract = result.get("contract", {})
    contract_view = (
        format_codex_execution_contract_view(contract)
        if isinstance(contract, dict)
        else "Contract: none"
    )
    stdout = str(result.get("stdout", "") or "none")
    stderr = str(result.get("stderr", "") or "none")
    return_code = result.get("return_code")
    return_code_text = "none" if return_code is None else str(return_code)

    lines = [
        f"Executed: {'yes' if result.get('executed') else 'no'}",
        f"Blocked: {'yes' if result.get('blocked') else 'no'}",
        f"Return code: {return_code_text}",
        f"Timed out: {'yes' if result.get('timed_out') else 'no'}",
        f"Message: {result.get('message', '')}",
        "Contract:",
        contract_view,
        f"Stdout: {stdout}",
        f"Stderr: {stderr}",
    ]
    if "post_review_ran" in result:
        lines.extend(
            [
                f"Post-Codex review ran: {'yes' if result.get('post_review_ran') else 'no'}",
                f"Post-Codex review decision: {result.get('post_review_decision', 'not run')}",
                f"Post-Codex review message: {result.get('post_review_message', '')}",
            ]
        )
        if result.get("post_review_report"):
            lines.append(f"Post-Codex review report:\n{result.get('post_review_report', '')}")
    return "\n".join(lines)
