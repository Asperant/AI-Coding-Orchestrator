from __future__ import annotations

import os
import re
from typing import Mapping


ALLOWED_PROVIDERS = {"disabled", "openai", "mock", "gemini"}
MAX_TIMEOUT_SECONDS = 600
MAX_CONTEXT_CHARS_CAP = 20000
SAFE_ENV_VAR_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")


def _build_safety_notes() -> list[str]:
    return [
        "Real LLM provider execution is not active in this boundary.",
        "API key values are read from environment variables and are never printed.",
        "Only provider metadata and safe availability checks are returned.",
        "No LLM, API, tool, or file execution is performed by this provider boundary.",
    ]


def _normalize_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _normalize_int(value: object, default: int) -> int:
    if isinstance(value, int):
        return value
    if value is None or value == "":
        return default
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _config_section(config: Mapping[str, object] | None) -> dict[str, object]:
    if config is None:
        return {}
    section = config.get("llm_provider")
    if isinstance(section, dict):
        return dict(section)
    return {}


def _provider_requires_api_key(provider: str) -> bool:
    return provider in ("openai", "gemini")


def _validate_provider(provider: str, blocked_reasons: list[str]) -> None:
    if provider not in ALLOWED_PROVIDERS:
        blocked_reasons.append(f"Unknown LLM provider: {provider}")


def _validate_safe_env_var_name(api_key_env_var: str | None, blocked_reasons: list[str]) -> str | None:
    if not api_key_env_var:
        return None
    normalized = str(api_key_env_var).strip()
    if not SAFE_ENV_VAR_RE.fullmatch(normalized):
        blocked_reasons.append("API key env var name is invalid or unsafe.")
        return None
    return normalized


def load_llm_provider_config(
    config: Mapping[str, object] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    provider_override: str | None = None,
    model_override: str | None = None,
    api_key_env_var_override: str | None = None,
    enabled_override: bool | None = None,
) -> dict[str, object]:
    provider_config = _config_section(config)
    effective_env: Mapping[str, str] = os.environ if env is None else env
    blocked_reasons: list[str] = []

    provider = str(
        provider_override
        or effective_env.get("LLM_PROVIDER")
        or provider_config.get("provider")
        or "disabled"
    ).strip().lower()
    model = str(
        model_override
        or effective_env.get("LLM_MODEL")
        or provider_config.get("model")
        or ""
    ).strip()
    configured_api_key_env_var = (
        api_key_env_var_override
        or effective_env.get("LLM_API_KEY_ENV")
        or provider_config.get("api_key_env_var")
    )
    enabled = (
        enabled_override
        if enabled_override is not None
        else _normalize_bool(
            effective_env.get("LLM_ENABLED", provider_config.get("enabled")),
            default=False,
        )
    )
    max_context_chars = _normalize_int(
        effective_env.get("LLM_MAX_CONTEXT_CHARS", provider_config.get("max_context_chars")),
        default=12000,
    )
    timeout_seconds = _normalize_int(
        effective_env.get("LLM_TIMEOUT_SECONDS", provider_config.get("timeout_seconds")),
        default=60,
    )

    _validate_provider(provider, blocked_reasons)

    if enabled and not model:
        blocked_reasons.append("Model name is required when the LLM provider is enabled.")

    if timeout_seconds <= 0 or timeout_seconds > MAX_TIMEOUT_SECONDS:
        blocked_reasons.append(
            f"Timeout must be greater than zero and no more than {MAX_TIMEOUT_SECONDS} seconds."
        )

    if max_context_chars <= 0 or max_context_chars > MAX_CONTEXT_CHARS_CAP:
        blocked_reasons.append(
            f"Max context chars must be greater than zero and no more than {MAX_CONTEXT_CHARS_CAP}."
        )

    api_key_env_var = _validate_safe_env_var_name(
        str(configured_api_key_env_var).strip() if configured_api_key_env_var else None,
        blocked_reasons,
    )
    if provider == "openai" and api_key_env_var is None:
        api_key_env_var = "OPENAI_API_KEY"
    elif provider == "gemini" and api_key_env_var is None:
        api_key_env_var = "GEMINI_API_KEY"

    api_key_present = bool(api_key_env_var and effective_env.get(api_key_env_var))
    if enabled and _provider_requires_api_key(provider) and not api_key_present:
        blocked_reasons.append("Configured API key environment variable is missing or empty.")

    blocked_reasons = list(dict.fromkeys(blocked_reasons))

    available = enabled and not blocked_reasons and (
        not _provider_requires_api_key(provider) or api_key_present
    )

    if provider == "disabled":
        risk_level = "low"
    elif blocked_reasons:
        risk_level = "high"
    else:
        risk_level = "medium"

    return {
        "provider": provider,
        "model": model or "none",
        "enabled": enabled,
        "available": available,
        "api_key_present": api_key_present,
        "api_key_env_var": api_key_env_var or "none",
        "max_context_chars": max_context_chars,
        "timeout_seconds": timeout_seconds,
        "risk_level": risk_level,
        "blocked_reasons": blocked_reasons or ["none"],
        "safety_notes": _build_safety_notes(),
    }


def format_llm_provider_config(result: dict[str, object]) -> str:
    blocked_reasons = list(result.get("blocked_reasons", [])) or ["none"]
    safety_notes = list(result.get("safety_notes", [])) or ["none"]
    return "\n".join(
        [
            f"Provider: {result.get('provider', 'disabled')}",
            f"Model: {result.get('model', 'none')}",
            f"Enabled: {'yes' if result.get('enabled') else 'no'}",
            f"Available: {'yes' if result.get('available') else 'no'}",
            f"API key present: {'yes' if result.get('api_key_present') else 'no'}",
            f"API key env var: {result.get('api_key_env_var', 'none')}",
            f"Max context chars: {result.get('max_context_chars', 'none')}",
            f"Timeout seconds: {result.get('timeout_seconds', 'none')}",
            f"Risk level: {result.get('risk_level', 'low')}",
            f"Blocked reasons: {'; '.join(str(item) for item in blocked_reasons)}",
            f"Safety notes: {'; '.join(str(item) for item in safety_notes)}",
        ]
    )
