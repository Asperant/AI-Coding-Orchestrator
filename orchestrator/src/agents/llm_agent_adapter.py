from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Protocol, TypedDict

from core.safety import guard_text_output


class LLMAdapterResult(TypedDict):
    executed: bool
    fallback_required: bool
    agent_role: str
    output_text: str
    safety_notes: list[str]
    error: str | None


class LLMAdapter(Protocol):
    def run_agent(
        self,
        *,
        agent_role: str,
        task_text: str,
        context_text: str | None = None,
        contract_result: dict[str, object],
        provider_config: dict[str, object] | None = None,
    ) -> LLMAdapterResult: ...


def _base_safety_notes() -> list[str]:
    return [
        "No real LLM or API call was performed.",
        "No tool execution was performed by the adapter.",
        "Deterministic fallback remains available.",
    ]


def _blocked_result(
    *,
    agent_role: str,
    output_text: str,
    error: str | None,
    contract_result: dict[str, object],
    adapter_note: str,
) -> LLMAdapterResult:
    blocked_reasons = list(contract_result.get("blocked_reasons", []))
    safety_notes = _base_safety_notes()
    safety_notes.append(adapter_note)
    if blocked_reasons and blocked_reasons != ["none"]:
        safety_notes.append(f"Contract blocked reasons: {'; '.join(str(item) for item in blocked_reasons)}")

    return {
        "executed": False,
        "fallback_required": True,
        "agent_role": agent_role,
        "output_text": output_text,
        "safety_notes": safety_notes,
        "error": error,
    }


def _provider_summary(provider_config: dict[str, object] | None) -> str:
    if not provider_config:
        return "Provider config was not supplied."
    return (
        f"Provider={provider_config.get('provider', 'disabled')}; "
        f"available={'yes' if provider_config.get('available') else 'no'}; "
        f"model={provider_config.get('model', 'none')}."
    )


def _openai_prompt(agent_role: str, task_text: str, context_text: str | None) -> str:
    prompt_lines = [
        f"Role: {agent_role}",
        f"Task: {task_text}",
        "Return a concise structured response with findings, risks, required fixes, and suggested tests.",
    ]
    if context_text:
        prompt_lines.append(f"Context:\n{context_text}")
    return "\n\n".join(prompt_lines)


def _import_openai_module() -> object:
    return importlib.import_module("openai")


def _import_gemini_module() -> object:
    return importlib.import_module("google.genai")


def _extract_openai_text(response: object) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    choices = getattr(response, "choices", None)
    if choices:
        first_choice = choices[0]
        message = getattr(first_choice, "message", None)
        content = getattr(message, "content", None)
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            text_parts = []
            for item in content:
                text_value = getattr(item, "text", None)
                if isinstance(text_value, str) and text_value.strip():
                    text_parts.append(text_value.strip())
            if text_parts:
                return "\n".join(text_parts)

    return ""


class DisabledLLMAdapter:
    def run_agent(
        self,
        *,
        agent_role: str,
        task_text: str,
        context_text: str | None = None,
        contract_result: dict[str, object],
        provider_config: dict[str, object] | None = None,
    ) -> LLMAdapterResult:
        del task_text, context_text

        if not bool(contract_result.get("can_run_llm_agent")):
            return _blocked_result(
                agent_role=agent_role,
                output_text="Disabled adapter refused execution because the LLM agent contract did not pass.",
                error="LLM agent contract blocked execution.",
                contract_result=contract_result,
                adapter_note=(
                    "DisabledLLMAdapter never attempts real execution. "
                    + _provider_summary(provider_config)
                ),
            )

        return _blocked_result(
            agent_role=agent_role,
            output_text="Disabled adapter refused execution. Use deterministic fallback instead.",
            error="DisabledLLMAdapter never runs LLM-backed agents.",
            contract_result=contract_result,
            adapter_note=(
                "DisabledLLMAdapter is a safety stub and always refuses execution. "
                + _provider_summary(provider_config)
            ),
        )


def _mock_output_for_role(agent_role: str) -> str:
    outputs = {
        "Planner": "Mock Planner output: confirm scope, keep the plan narrow, and review the first implementation step.",
        "Reviewer": "Mock Reviewer output: inspect changed paths for regressions, edge cases, and missing validation.",
        "Tester": "Mock Tester output: run focused regression, negative-path, and smoke checks around the affected paths.",
        "Security": "Mock Security output: review secrets, auth, data exposure, and permission boundaries before approval.",
        "Architect": "Mock Architect output: validate module boundaries, caller impact, and long-term maintainability risks.",
        "Product": "Mock Product output: verify user-facing flow, copy clarity, and MVP scope before rollout.",
        "Release": "Mock Release output: check config, packaging, rollout safety, and rollback expectations.",
    }
    return outputs.get(
        agent_role,
        "Mock agent output: deterministic fallback summary is available.",
    )


class MockLLMAdapter:
    def run_agent(
        self,
        *,
        agent_role: str,
        task_text: str,
        context_text: str | None = None,
        contract_result: dict[str, object],
        provider_config: dict[str, object] | None = None,
    ) -> LLMAdapterResult:
        del task_text, context_text

        if not bool(contract_result.get("can_run_llm_agent")):
            return _blocked_result(
                agent_role=agent_role,
                output_text="Mock adapter refused execution because the LLM agent contract did not pass.",
                error="LLM agent contract blocked mock execution.",
                contract_result=contract_result,
                adapter_note=(
                    "MockLLMAdapter only returns canned output when the contract passes. "
                    + _provider_summary(provider_config)
                ),
            )

        safety_notes = _base_safety_notes()
        safety_notes.append(
            "MockLLMAdapter returned deterministic canned output for testing. "
            + _provider_summary(provider_config)
        )

        return {
            "executed": True,
            "fallback_required": False,
            "agent_role": agent_role,
            "output_text": _mock_output_for_role(agent_role),
            "safety_notes": safety_notes,
            "error": None,
        }


class OpenAILLMAdapter:
    def run_agent(
        self,
        *,
        agent_role: str,
        task_text: str,
        context_text: str | None = None,
        contract_result: dict[str, object],
        provider_config: dict[str, object] | None = None,
    ) -> LLMAdapterResult:
        provider_config = provider_config or {}

        if not bool(contract_result.get("can_run_llm_agent")):
            return _blocked_result(
                agent_role=agent_role,
                output_text="OpenAI adapter refused execution because the LLM agent contract did not pass.",
                error="LLM agent contract blocked OpenAI execution.",
                contract_result=contract_result,
                adapter_note="OpenAILLMAdapter requires a passing contract.",
            )

        provider = str(provider_config.get("provider", "disabled"))
        if provider != "openai":
            return _blocked_result(
                agent_role=agent_role,
                output_text="OpenAI adapter refused execution because the provider is not configured as openai.",
                error="OpenAI provider is not selected.",
                contract_result=contract_result,
                adapter_note=_provider_summary(provider_config),
            )

        if not bool(provider_config.get("enabled")):
            return _blocked_result(
                agent_role=agent_role,
                output_text="OpenAI adapter refused execution because the provider is disabled.",
                error="OpenAI provider is disabled.",
                contract_result=contract_result,
                adapter_note=_provider_summary(provider_config),
            )

        if not bool(provider_config.get("available")):
            return _blocked_result(
                agent_role=agent_role,
                output_text="OpenAI adapter refused execution because the provider is unavailable.",
                error="OpenAI provider is unavailable or blocked.",
                contract_result=contract_result,
                adapter_note=_provider_summary(provider_config),
            )

        api_key_env_var = str(provider_config.get("api_key_env_var", "none"))
        api_key_value = None if api_key_env_var == "none" else __import__("os").environ.get(api_key_env_var)
        if not api_key_value:
            return _blocked_result(
                agent_role=agent_role,
                output_text="OpenAI adapter refused execution because the configured API key environment variable is missing.",
                error="Configured OpenAI API key environment variable is missing.",
                contract_result=contract_result,
                adapter_note=f"API key env var checked: {api_key_env_var}",
            )

        max_context_chars = int(provider_config.get("max_context_chars", 12000))
        timeout_seconds = int(provider_config.get("timeout_seconds", 60))
        safe_context_text = None if context_text is None else str(context_text)
        if safe_context_text and len(safe_context_text) > max_context_chars:
            return _blocked_result(
                agent_role=agent_role,
                output_text="OpenAI adapter refused execution because the context exceeds the configured maximum size.",
                error="OpenAI adapter context exceeds configured maximum size.",
                contract_result=contract_result,
                adapter_note=f"Configured max context chars: {max_context_chars}",
            )

        prompt_text = _openai_prompt(agent_role, task_text, safe_context_text)

        try:
            openai_module = _import_openai_module()
        except ImportError:
            return _blocked_result(
                agent_role=agent_role,
                output_text="OpenAI adapter is unavailable because the OpenAI SDK is not installed.",
                error="OpenAI SDK is not installed.",
                contract_result=contract_result,
                adapter_note="Install the OpenAI SDK before enabling the real provider path.",
            )

        try:
            client = openai_module.OpenAI(api_key=api_key_value, timeout=timeout_seconds)
            response = client.responses.create(
                model=str(provider_config.get("model", "")),
                input=prompt_text,
            )
            output_text = _extract_openai_text(response)
        except Exception as exc:
            return _blocked_result(
                agent_role=agent_role,
                output_text="OpenAI adapter failed and fell back safely.",
                error=f"OpenAI API call failed: {type(exc).__name__}",
                contract_result=contract_result,
                adapter_note=_provider_summary(provider_config),
            )

        output_guard_result = guard_text_output(output_text, "OpenAI agent output")
        if not output_guard_result["allowed"]:
            return _blocked_result(
                agent_role=agent_role,
                output_text=str(output_guard_result["safe_message"]),
                error="OpenAI output contained secret-like content and was blocked.",
                contract_result=contract_result,
                adapter_note="OpenAI output was blocked by the safety guard.",
            )

        safety_notes = [
            "OpenAI adapter executed through configured provider boundary.",
            "No tool execution was performed by the adapter.",
            "Raw API key values were not printed or returned.",
            _provider_summary(provider_config),
        ]
        return {
            "executed": True,
            "fallback_required": False,
            "agent_role": agent_role,
            "output_text": output_text or "OpenAI adapter returned an empty response.",
            "safety_notes": safety_notes,
            "error": None,
        }


class GeminiLLMAdapter:
    def run_agent(
        self,
        *,
        agent_role: str,
        task_text: str,
        context_text: str | None = None,
        contract_result: dict[str, object],
        provider_config: dict[str, object] | None = None,
    ) -> LLMAdapterResult:
        provider_config = provider_config or {}

        if not bool(contract_result.get("can_run_llm_agent")):
            return _blocked_result(
                agent_role=agent_role,
                output_text="Gemini adapter refused execution because the LLM agent contract did not pass.",
                error="LLM agent contract blocked Gemini execution.",
                contract_result=contract_result,
                adapter_note="GeminiLLMAdapter requires a passing contract.",
            )

        provider = str(provider_config.get("provider", "disabled"))
        if provider != "gemini":
            return _blocked_result(
                agent_role=agent_role,
                output_text="Gemini adapter refused execution because the provider is not configured as gemini.",
                error="Gemini provider is not selected.",
                contract_result=contract_result,
                adapter_note=_provider_summary(provider_config),
            )

        if not bool(provider_config.get("enabled")):
            return _blocked_result(
                agent_role=agent_role,
                output_text="Gemini adapter refused execution because the provider is disabled.",
                error="Gemini provider is disabled.",
                contract_result=contract_result,
                adapter_note=_provider_summary(provider_config),
            )

        if not bool(provider_config.get("available")):
            return _blocked_result(
                agent_role=agent_role,
                output_text="Gemini adapter refused execution because the provider is unavailable.",
                error="Gemini provider is unavailable or blocked.",
                contract_result=contract_result,
                adapter_note=_provider_summary(provider_config),
            )

        api_key_env_var = str(provider_config.get("api_key_env_var", "none"))
        api_key_value = None if api_key_env_var == "none" else __import__("os").environ.get(api_key_env_var)
        if not api_key_value:
            return _blocked_result(
                agent_role=agent_role,
                output_text="Gemini adapter refused execution because the configured API key environment variable is missing.",
                error="Configured Gemini API key environment variable is missing.",
                contract_result=contract_result,
                adapter_note=f"API key env var checked: {api_key_env_var}",
            )

        max_context_chars = int(provider_config.get("max_context_chars", 12000))
        safe_context_text = None if context_text is None else str(context_text)
        if safe_context_text and len(safe_context_text) > max_context_chars:
            return _blocked_result(
                agent_role=agent_role,
                output_text="Gemini adapter refused execution because the context exceeds the configured maximum size.",
                error="Gemini adapter context exceeds configured maximum size.",
                contract_result=contract_result,
                adapter_note=f"Configured max context chars: {max_context_chars}",
            )

        prompt_text = _openai_prompt(agent_role, task_text, safe_context_text)

        try:
            genai_module = _import_gemini_module()
        except ImportError:
            return _blocked_result(
                agent_role=agent_role,
                output_text="Gemini adapter is unavailable because the google-genai SDK is not installed.",
                error="google-genai SDK is not installed.",
                contract_result=contract_result,
                adapter_note="Install the google-genai SDK before enabling the real provider path.",
            )

        try:
            client = genai_module.Client(api_key=api_key_value)
            response = client.models.generate_content(
                model=str(provider_config.get("model", "")),
                contents=prompt_text,
            )
            output_text = getattr(response, "text", "")
            if not isinstance(output_text, str) or not output_text.strip():
                output_text = ""
            else:
                output_text = output_text.strip()
        except Exception as exc:
            return _blocked_result(
                agent_role=agent_role,
                output_text="Gemini adapter failed and fell back safely.",
                error=f"Gemini API call failed: {type(exc).__name__}",
                contract_result=contract_result,
                adapter_note=_provider_summary(provider_config),
            )

        output_guard_result = guard_text_output(output_text, "Gemini agent output")
        if not output_guard_result["allowed"]:
            return _blocked_result(
                agent_role=agent_role,
                output_text=str(output_guard_result["safe_message"]),
                error="Gemini output contained secret-like content and was blocked.",
                contract_result=contract_result,
                adapter_note="Gemini output was blocked by the safety guard.",
            )

        safety_notes = [
            "Gemini adapter executed through configured provider boundary.",
            "No tool execution was performed by the adapter.",
            "Raw API key values were not printed or returned.",
            _provider_summary(provider_config),
        ]
        return {
            "executed": True,
            "fallback_required": False,
            "agent_role": agent_role,
            "output_text": output_text or "Gemini adapter returned an empty response.",
            "safety_notes": safety_notes,
            "error": None,
        }


def get_llm_adapter(adapter_name: str) -> LLMAdapter:
    normalized_name = str(adapter_name).strip().lower()
    if normalized_name == "mock":
        return MockLLMAdapter()
    if normalized_name == "openai":
        return OpenAILLMAdapter()
    if normalized_name == "gemini":
        return GeminiLLMAdapter()
    return DisabledLLMAdapter()


def format_llm_agent_adapter_result(result: dict[str, object]) -> str:
    safety_notes = list(result.get("safety_notes", [])) or ["none"]
    return "\n".join(
        [
            f"Executed: {'yes' if result.get('executed') else 'no'}",
            f"Fallback required: {'yes' if result.get('fallback_required') else 'no'}",
            f"Agent role: {result.get('agent_role', '')}",
            f"Output text: {result.get('output_text', '')}",
            f"Safety notes: {'; '.join(str(item) for item in safety_notes)}",
            f"Error: {result.get('error', 'none') or 'none'}",
        ]
    )
