from __future__ import annotations

from typing import Literal, TypedDict

from agents.llm_agent_adapter import get_llm_adapter
from agents.llm_agent_contract import evaluate_llm_agent_contract
from agents.llm_provider_config import load_llm_provider_config
from agents.agent_decision import aggregate_agent_decisions


AgentRole = Literal["Planner", "Reviewer", "Tester", "Security", "Architect", "Product", "Release"]
AgentRuntimeMode = Literal["deterministic", "mock", "disabled", "openai", "gemini"]


class AgentInput(TypedDict, total=False):
    role: AgentRole
    task_text: str
    mode: str
    task_classification: dict[str, object] | None
    changed_files: list[str]
    diff_text: str
    project_context: dict[str, object] | None
    is_git_repo: bool
    diff_present: bool
    llm_mode: AgentRuntimeMode
    llm_enabled: bool
    llm_approval_confirmed: bool
    context_text: str | None
    context_sources: list[str]
    llm_provider: str | None
    llm_model: str | None
    llm_api_key_env_var: str | None


class AgentResult(TypedDict, total=False):
    role: AgentRole
    findings: list[str]
    risks: list[str]
    required_fixes: list[str]
    suggested_tests: list[str]
    decision_dict: dict[str, object]
    runtime_mode: AgentRuntimeMode
    llm_adapter_used: str
    fallback_used: bool
    safety_notes: list[str]
    llm_provider: str
    provider_available: bool
    provider_execution_status: str
    fallback_reason: str | None


class AgentRunSummary(TypedDict, total=False):
    agents_used: list[AgentRole]
    per_agent_results: list[AgentResult]
    consolidated_findings: list[str]
    risks: list[str]
    required_fixes: list[str]
    suggested_tests: list[str]
    decision_hint: str
    multi_agent_decision: dict[str, object]
    runtime_mode: AgentRuntimeMode
    llm_adapter_used: str
    fallback_used: bool
    runtime_notes: list[str]
    llm_provider: str
    provider_available: bool
    provider_execution_status: str
    fallback_reason: str | None


SECURITY_KEYWORDS = (
    "auth",
    "token",
    "secret",
    "password",
    "env",
    "firebase",
    "supabase",
    "database",
    "user data",
)
ARCHITECT_KEYWORDS = ("context", "services", "architecture", "config", "routing")
PRODUCT_KEYWORDS = ("ui copy", "labels", "onboarding", "result", "permission", "product text")
PRODUCT_FILE_KEYWORDS = ("ui", "copy", "label", "onboarding", "result", "permission", "product")
RELEASE_KEYWORDS = ("config", "env", "build", "dependency", "package", "deploy", "migration", "release")
TEST_KEYWORDS = ("test", "tests", "spec", "smoke")
DOC_FILE_KEYWORDS = ("readme", "docs/")
HIGH_RISK_TASK_TYPES = {"security/privacy change", "database change", "release/deploy review"}
PRODUCT_TASK_TYPES = {"feature", "UI change"}


def _combined_text(changed_files: list[str], diff_text: str, task_text: str) -> str:
    return " ".join(changed_files).lower() + " " + diff_text.lower() + " " + task_text.lower()


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _is_docs_only_change(changed_files: list[str]) -> bool:
    return bool(changed_files) and all(
        path.lower().startswith("docs/") or "readme" in path.lower() for path in changed_files
    )


def _is_core_file(path: str) -> bool:
    return path.startswith("src/") or path in {"src/main.py", "src/cli.py"}


def _task_type(task_classification: dict[str, object] | None) -> str | None:
    if task_classification is None:
        return None
    return str(task_classification.get("primary_task_type"))


def _runtime_context_text(
    *,
    explicit_context_text: str | None,
    changed_files: list[str],
    diff_text: str,
    project_context: dict[str, object] | None,
) -> str:
    if explicit_context_text is not None:
        return str(explicit_context_text)

    context_parts: list[str] = []
    if changed_files:
        context_parts.append("Changed files: " + ", ".join(changed_files))
    if diff_text:
        context_parts.append(diff_text)
    if project_context is not None:
        context_parts.append(str(project_context))
    return "\n".join(context_parts)


def _select_agents(
    *,
    mode: str,
    changed_files: list[str],
    diff_text: str,
    task_text: str,
    task_classification: dict[str, object] | None,
) -> list[AgentRole]:
    task_type = _task_type(task_classification)
    combined_text = _combined_text(changed_files, diff_text, task_text)
    agents: list[AgentRole] = []

    if mode in {"plan", "run", "pre-codex"}:
        agents.append("Planner")
    if mode == "review-diff":
        agents.extend(["Reviewer", "Tester"])
    elif mode == "pre-codex":
        agents.append("Tester")

    if task_type == "security/privacy change" or _contains_any(combined_text, SECURITY_KEYWORDS):
        agents.append("Security")

    core_files_changed = [path for path in changed_files if _is_core_file(path)]
    if (
        task_type == "refactor"
        or len(core_files_changed) > 1
        or _contains_any(combined_text, ARCHITECT_KEYWORDS)
    ):
        agents.append("Architect")

    if task_type in PRODUCT_TASK_TYPES or _contains_any(combined_text, PRODUCT_KEYWORDS) or _contains_any(
        combined_text, PRODUCT_FILE_KEYWORDS
    ):
        agents.append("Product")

    if task_type == "release/deploy review" or _contains_any(combined_text, RELEASE_KEYWORDS):
        agents.append("Release")

    deduped: list[AgentRole] = []
    for agent in agents:
        if agent not in deduped:
            deduped.append(agent)
    return deduped


def run_agent_pass(agent_input: AgentInput) -> AgentResult:
    role = agent_input["role"]
    changed_files = list(agent_input.get("changed_files", []))
    diff_text = str(agent_input.get("diff_text", ""))
    task_text = str(agent_input.get("task_text", ""))
    mode = str(agent_input.get("mode", "review-diff"))
    task_type = _task_type(agent_input.get("task_classification"))
    combined_text = _combined_text(changed_files, diff_text, task_text)
    is_git_repo = bool(agent_input.get("is_git_repo", False))
    diff_present = bool(agent_input.get("diff_present", False))
    llm_mode = agent_input.get("llm_mode", "deterministic")
    llm_enabled = bool(agent_input.get("llm_enabled", False))
    llm_approval_confirmed = bool(agent_input.get("llm_approval_confirmed", False))
    explicit_context_text = agent_input.get("context_text")
    context_sources = list(agent_input.get("context_sources", []))
    llm_provider = agent_input.get("llm_provider")
    llm_model = agent_input.get("llm_model")
    llm_api_key_env_var = agent_input.get("llm_api_key_env_var")

    findings: list[str] = []
    risks: list[str] = []
    required_fixes: list[str] = []
    suggested_tests: list[str] = []

    if role == "Planner":
        findings.append(f"Planner classified the work as {task_type or 'unknown'} in {mode} mode.")
        if mode == "run":
            findings.append("Planner prepared a gated execution path before any implementation step.")
        risks.append("Implementation should stay scoped to explicitly allowed files.")
        required_fixes.append("Confirm the scoped plan before proceeding with execution.")
        suggested_tests.append("Verify the planned scope matches the requested task and allowed files.")

    elif role == "Reviewer":
        findings.append(f"Reviewer inspected {len(changed_files)} changed file(s).")
        if not is_git_repo:
            required_fixes.append("Use a git repository if you want a diff-based review.")
        elif not diff_present:
            required_fixes.append("Provide actual git changes before requesting diff review.")
        elif task_type == "documentation change" and _contains_any(combined_text, DOC_FILE_KEYWORDS):
            findings.append("Changes appear documentation-focused.")

    elif role == "Tester":
        findings.append("Tester did not execute tests in this review pass.")
        if changed_files:
            findings.append(f"Tester should focus on: {', '.join(changed_files)}.")
            suggested_tests.append(f"Run focused checks for: {', '.join(changed_files)}.")
        if task_type == "bug fix":
            suggested_tests.append("Reproduce the reported failure and verify the regression path.")
        elif task_type == "feature":
            suggested_tests.append("Check success, error, and empty-state behavior for the new flow.")
        elif task_type == "refactor":
            suggested_tests.append("Run behavior-preserving regression tests around changed modules.")
        elif task_type in HIGH_RISK_TASK_TYPES:
            suggested_tests.append("Add negative-path validation for sensitive or migration-related behavior.")
        else:
            suggested_tests.append("Run the closest unit or smoke tests for the changed behavior.")

    elif role == "Security":
        findings.append("Security lens flagged auth, secret, database, or user-data related change indicators.")
        risks.append("Sensitive behavior may require stricter validation before approval.")
        required_fixes.append("Verify auth, secret, database, and user-data handling before approval.")

    elif role == "Architect":
        findings.append("Architect lens flagged cross-module or structural impact.")
        risks.append("Cross-file changes can cause hidden caller or boundary regressions.")
        required_fixes.append("Review cross-module boundaries and impacted callers.")

    elif role == "Product":
        findings.append("Product lens flagged user-facing behavior or copy impact.")
        risks.append("User-facing behavior and copy should be checked against expected flow.")

    elif role == "Release":
        findings.append("Release lens flagged config, deploy, package, or migration impact.")
        risks.append("Config or release-related changes can affect rollout and rollback safety.")
        required_fixes.append("Verify config or release changes and confirm rollback assumptions.")

    if role in {"Reviewer", "Tester"} and diff_present and not _is_docs_only_change(changed_files):
        if not _contains_any(combined_text, TEST_KEYWORDS) and task_type not in {"test writing", "documentation change"}:
            required_fixes.append("Add or run targeted regression tests for the changed paths.")

    runtime_mode: AgentRuntimeMode = "deterministic"
    llm_adapter_used = "none"
    fallback_used = False
    safety_notes = ["Deterministic agent runtime is the default execution path."]
    provider_name = "disabled"
    provider_available = False
    provider_execution_status = "not requested"
    fallback_reason = None

    if llm_mode != "deterministic":
        runtime_mode = llm_mode
        runtime_context_text = _runtime_context_text(
            explicit_context_text=explicit_context_text,
            changed_files=changed_files,
            diff_text=diff_text,
            project_context=agent_input.get("project_context"),
        )
        provider_override = (
            str(llm_provider).strip().lower()
            if llm_provider is not None
            else ("mock" if llm_mode == "mock" else ("openai" if llm_mode == "openai" else ("gemini" if llm_mode == "gemini" else "disabled")))
        )
        provider_config_result = load_llm_provider_config(
            {
                "llm_provider": {
                    "provider": provider_override,
                    "model": llm_model or "",
                    "api_key_env_var": llm_api_key_env_var or "",
                    "enabled": llm_enabled,
                }
            },
            provider_override=provider_override,
            model_override=llm_model,
            api_key_env_var_override=llm_api_key_env_var,
            enabled_override=llm_enabled,
        )
        provider_name = str(provider_config_result["provider"])
        provider_available = bool(provider_config_result["available"])
        safety_notes.extend(str(note) for note in provider_config_result["safety_notes"])
        llm_contract_result = evaluate_llm_agent_contract(
            role,
            task_text,
            context_text=runtime_context_text or None,
            allowed_context_sources=context_sources,
            approval_confirmed=llm_approval_confirmed,
            llm_enabled=llm_enabled,
        )
        if provider_name == "mock":
            llm_adapter_used = "mock"
            provider_execution_status = "mock adapter executed" if provider_available else "mock provider unavailable"
            llm_adapter_result = get_llm_adapter("mock").run_agent(
                agent_role=role,
                task_text=task_text,
                context_text=runtime_context_text or None,
                contract_result=llm_contract_result,
                provider_config=provider_config_result,
            )
            safety_notes.extend(str(note) for note in llm_adapter_result["safety_notes"])

            if llm_adapter_result["executed"]:
                findings.append(str(llm_adapter_result["output_text"]))
            else:
                fallback_used = True
                fallback_reason = "Mock provider contract did not pass."
                provider_execution_status = "mock adapter blocked"
                findings.append(
                    f"{role} used deterministic fallback because mock LLM adapter execution was not available."
                )
                for blocked_reason in list(llm_contract_result.get("blocked_reasons", [])):
                    if blocked_reason != "none" and blocked_reason not in risks:
                        risks.append(str(blocked_reason))
        elif provider_name == "openai":
            llm_adapter_used = "openai"
            llm_adapter_result = get_llm_adapter("openai").run_agent(
                agent_role=role,
                task_text=task_text,
                context_text=runtime_context_text or None,
                contract_result=llm_contract_result,
                provider_config=provider_config_result,
            )
            safety_notes.extend(str(note) for note in llm_adapter_result["safety_notes"])

            if llm_adapter_result["executed"]:
                provider_execution_status = "openai adapter executed"
                findings.append(str(llm_adapter_result["output_text"]))
            else:
                fallback_used = True
                provider_execution_status = (
                    "openai adapter blocked" if provider_available else "real provider unavailable"
                )
                fallback_reason = str(llm_adapter_result.get("error") or "OpenAI execution was blocked.")
                findings.append(
                    f"{role} used deterministic fallback because OpenAI adapter execution was not available."
                )
                if llm_adapter_result.get("output_text"):
                    findings.append(str(llm_adapter_result["output_text"]))
                for blocked_reason in list(provider_config_result.get("blocked_reasons", [])):
                    if blocked_reason != "none" and blocked_reason not in risks:
                        risks.append(str(blocked_reason))
                for blocked_reason in list(llm_contract_result.get("blocked_reasons", [])):
                    if blocked_reason != "none" and blocked_reason not in risks:
                        risks.append(str(blocked_reason))
        elif provider_name == "gemini":
            llm_adapter_used = "gemini"
            llm_adapter_result = get_llm_adapter("gemini").run_agent(
                agent_role=role,
                task_text=task_text,
                context_text=runtime_context_text or None,
                contract_result=llm_contract_result,
                provider_config=provider_config_result,
            )
            safety_notes.extend(str(note) for note in llm_adapter_result["safety_notes"])

            if llm_adapter_result["executed"]:
                provider_execution_status = "gemini adapter executed"
                findings.append(str(llm_adapter_result["output_text"]))
            else:
                fallback_used = True
                provider_execution_status = (
                    "gemini adapter blocked" if provider_available else "real provider unavailable"
                )
                fallback_reason = str(llm_adapter_result.get("error") or "Gemini execution was blocked.")
                findings.append(
                    f"{role} used deterministic fallback because Gemini adapter execution was not available."
                )
                if llm_adapter_result.get("output_text"):
                    findings.append(str(llm_adapter_result["output_text"]))
                for blocked_reason in list(provider_config_result.get("blocked_reasons", [])):
                    if blocked_reason != "none" and blocked_reason not in risks:
                        risks.append(str(blocked_reason))
                for blocked_reason in list(llm_contract_result.get("blocked_reasons", [])):
                    if blocked_reason != "none" and blocked_reason not in risks:
                        risks.append(str(blocked_reason))
        elif provider_name == "disabled":
            llm_adapter_used = "disabled"
            fallback_used = True
            fallback_reason = "LLM provider is disabled."
            provider_execution_status = "provider disabled"
            safety_notes.append("Provider disabled forced deterministic fallback.")
            findings.append(
                f"{role} used deterministic fallback because the LLM provider is disabled."
            )
        else:
            llm_adapter_used = provider_name
            fallback_used = True
            fallback_reason = (
                f"Real provider {provider_name} is not implemented yet."
                if provider_available
                else f"Real provider {provider_name} is unavailable or blocked."
            )
            provider_execution_status = (
                "real provider configured but execution not implemented"
                if provider_available
                else "real provider unavailable"
            )
            safety_notes.append(
                f"Real provider {provider_name} is not executed yet. Deterministic fallback remained active."
            )
            findings.append(
                f"{role} used deterministic fallback because real provider {provider_name} execution is not implemented yet."
            )
            for blocked_reason in list(provider_config_result.get("blocked_reasons", [])):
                if blocked_reason != "none" and blocked_reason not in risks:
                    risks.append(str(blocked_reason))
            for blocked_reason in list(llm_contract_result.get("blocked_reasons", [])):
                if blocked_reason != "none" and blocked_reason not in risks:
                    risks.append(str(blocked_reason))

    decision = "approve"
    if required_fixes and any(rf != "none" for rf in required_fixes):
        decision = "needs_changes"
    if not is_git_repo and role == "Reviewer":
        decision = "block"
        blocked_reasons = ["Not a git repository."]
    elif not diff_present and role == "Reviewer":
        decision = "needs_context"
        blocked_reasons = []
    else:
        blocked_reasons = []
        
    risk_level = "low"
    if risks and any(r != "none" for r in risks):
        risk_level = "medium"
        if task_type in HIGH_RISK_TASK_TYPES or role in {"Security", "Release"}:
            risk_level = "high"
            
    decision_dict = {
        "agent_role": role,
        "decision": decision,
        "confidence": "high" if llm_mode == "deterministic" else "medium",
        "risk_level": risk_level,
        "findings": [f for f in findings if f != "none"],
        "required_fixes": [rf for rf in required_fixes if rf != "none"],
        "suggested_tests": [st for st in suggested_tests if st != "none"],
        "blocked_reasons": blocked_reasons,
        "next_action": "",
        "safety_notes": [n for n in safety_notes if n != "none"],
    }

    return {
        "role": role,
        "findings": findings or ["none"],
        "risks": risks or ["none"],
        "required_fixes": required_fixes or ["none"],
        "suggested_tests": suggested_tests or ["none"],
        "decision_dict": decision_dict,
        "runtime_mode": runtime_mode,
        "llm_adapter_used": llm_adapter_used,
        "fallback_used": fallback_used,
        "safety_notes": safety_notes,
        "llm_provider": provider_name,
        "provider_available": provider_available,
        "provider_execution_status": provider_execution_status,
        "fallback_reason": fallback_reason,
    }


def _build_decision_hint(
    *,
    mode: str,
    is_git_repo: bool,
    diff_present: bool,
    task_classification: dict[str, object] | None,
    agents_used: list[AgentRole],
    required_fixes: list[str],
) -> str:
    task_type = _task_type(task_classification)
    if mode == "review-diff":
        if not is_git_repo:
            return "Blocked"
        if not diff_present:
            return "Needs more context"
        if task_type in HIGH_RISK_TASK_TYPES or "Security" in agents_used or "Release" in agents_used:
            return "Needs revision"
        if required_fixes:
            return "Approved with changes"
        return "Approved"
    if mode == "plan":
        return "Needs more context" if task_type == "unknown" else "Approved"
    if mode in {"run", "pre-codex"}:
        return "Approved with changes" if required_fixes else "Approved"
    return "Needs more context"


def run_agent_workflow(
    *,
    task_text: str,
    mode: str,
    task_classification: dict[str, object] | None,
    changed_files: list[str] | None = None,
    diff_text: str = "",
    project_context: dict[str, object] | None = None,
    is_git_repo: bool = False,
    diff_present: bool = False,
    llm_mode: AgentRuntimeMode = "deterministic",
    llm_enabled: bool = False,
    llm_approval_confirmed: bool = False,
    context_text: str | None = None,
    context_sources: list[str] | None = None,
    llm_provider: str | None = None,
    llm_model: str | None = None,
    llm_api_key_env_var: str | None = None,
) -> AgentRunSummary:
    normalized_changed_files = list(changed_files or [])
    agents_used = _select_agents(
        mode=mode,
        changed_files=normalized_changed_files,
        diff_text=diff_text,
        task_text=task_text,
        task_classification=task_classification,
    )

    per_agent_results: list[AgentResult] = []
    consolidated_findings: list[str] = []
    risks: list[str] = []
    required_fixes: list[str] = []
    suggested_tests: list[str] = []
    runtime_notes: list[str] = []
    fallback_used = False
    llm_provider_name = "disabled"
    provider_available = False
    provider_execution_status = "not requested"
    fallback_reason = None
    llm_adapter_used = "none" if llm_mode == "deterministic" else llm_mode

    for role in agents_used:
        result = run_agent_pass(
            {
                "role": role,
                "task_text": task_text,
                "mode": mode,
                "task_classification": task_classification,
                "changed_files": normalized_changed_files,
                "diff_text": diff_text,
                "project_context": project_context,
                "is_git_repo": is_git_repo,
                "diff_present": diff_present,
                "llm_mode": llm_mode,
                "llm_enabled": llm_enabled,
                "llm_approval_confirmed": llm_approval_confirmed,
                "context_text": context_text,
                "context_sources": list(context_sources or []),
                "llm_provider": llm_provider,
                "llm_model": llm_model,
                "llm_api_key_env_var": llm_api_key_env_var,
            }
        )
        per_agent_results.append(result)
        for key, bucket in (
            ("findings", consolidated_findings),
            ("risks", risks),
            ("required_fixes", required_fixes),
            ("suggested_tests", suggested_tests),
        ):
            for item in result[key]:
                if item != "none" and item not in bucket:
                    bucket.append(item)
        for note in result.get("safety_notes", []):
            if note not in runtime_notes:
                runtime_notes.append(note)
        if result.get("fallback_used"):
            fallback_used = True
        llm_adapter_used = str(result.get("llm_adapter_used", llm_adapter_used))
        llm_provider_name = str(result.get("llm_provider", llm_provider_name))
        provider_available = bool(result.get("provider_available", provider_available))
        provider_execution_status = str(
            result.get("provider_execution_status", provider_execution_status)
        )
        if result.get("fallback_reason"):
            fallback_reason = str(result.get("fallback_reason"))

    if project_context is not None and project_context.get("missing_files"):
        partial_context_risk = "Project AI-ready docs are incomplete, so review context may be partial."
        if partial_context_risk not in risks:
            risks.append(partial_context_risk)

    return {
        "agents_used": agents_used,
        "per_agent_results": per_agent_results,
        "consolidated_findings": consolidated_findings or ["none"],
        "risks": risks or ["No elevated review risks were detected from the diff alone."],
        "required_fixes": required_fixes or ["none"],
        "suggested_tests": suggested_tests or ["none"],
        "decision_hint": _build_decision_hint(
            mode=mode,
            is_git_repo=is_git_repo,
            diff_present=diff_present,
            task_classification=task_classification,
            agents_used=agents_used,
            required_fixes=required_fixes,
        ),
        "multi_agent_decision": aggregate_agent_decisions([res["decision_dict"] for res in per_agent_results if "decision_dict" in res]),
        "runtime_mode": llm_mode,
        "llm_adapter_used": llm_adapter_used,
        "fallback_used": fallback_used,
        "runtime_notes": runtime_notes or ["Deterministic runtime path remained active."],
        "llm_provider": llm_provider_name,
        "provider_available": provider_available,
        "provider_execution_status": provider_execution_status,
        "fallback_reason": fallback_reason,
    }


def _first_non_none_items(items: list[str], limit: int = 2) -> list[str]:
    return [item for item in items if item and item != "none"][:limit]


def format_pre_codex_agent_guidance(summary: AgentRunSummary) -> str:
    agents_used = summary.get("agents_used", [])
    findings = _first_non_none_items(list(summary.get("consolidated_findings", [])), limit=2)
    risks = _first_non_none_items(list(summary.get("risks", [])), limit=2)
    suggested_tests = _first_non_none_items(list(summary.get("suggested_tests", [])), limit=2)
    runtime_notes = _first_non_none_items(list(summary.get("runtime_notes", [])), limit=2)

    scope_guidance = (
        "; ".join(findings)
        if findings
        else "Keep the implementation tightly scoped to the listed allowed files."
    )
    risk_guidance = (
        "; ".join(risks)
        if risks
        else "No elevated pre-execution risks were identified beyond normal scoped-change review."
    )
    test_guidance = (
        "; ".join(suggested_tests)
        if suggested_tests
        else "Run focused manual or automated checks for the changed paths."
    )
    safety_guidance = (
        "; ".join(runtime_notes)
        if runtime_notes
        else "Use the deterministic fallback and stop instead of guessing."
    )

    return "\n".join(
        [
            "Pre-Codex Agent Guidance:",
            f"- Agents used: {'; '.join(agents_used) or 'none'}",
            f"- Scope guidance: {scope_guidance}",
            f"- Risk guidance: {risk_guidance}",
            f"- Test guidance: {test_guidance}",
            f"- Safety guidance: {safety_guidance}",
        ]
    )


def format_agent_run_summary(summary: AgentRunSummary) -> str:
    return "\n".join(
        [
            f"Agent runtime mode: {summary.get('runtime_mode', 'deterministic')}",
            f"LLM adapter used: {summary.get('llm_adapter_used', 'none')}",
            f"LLM provider: {summary.get('llm_provider', 'disabled')}",
            f"Provider available: {'yes' if summary.get('provider_available') else 'no'}",
            f"Provider execution status: {summary.get('provider_execution_status', 'not requested')}",
            f"Fallback used: {'yes' if summary.get('fallback_used') else 'no'}",
            f"Fallback reason: {summary.get('fallback_reason') or 'none'}",
            f"Runtime notes: {'; '.join(summary.get('runtime_notes', ['none']))}",
            f"Agents used: {'; '.join(summary['agents_used']) or 'none'}",
            f"Consolidated findings: {'; '.join(summary['consolidated_findings'])}",
            f"Risks: {'; '.join(summary['risks'])}",
            f"Required fixes: {'; '.join(summary['required_fixes'])}",
            f"Suggested tests: {'; '.join(summary['suggested_tests'])}",
            f"Decision hint: {summary['decision_hint']}",
        ]
    )
