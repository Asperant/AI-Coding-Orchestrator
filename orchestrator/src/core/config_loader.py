from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "default.yaml"
APPROVED_PATHS_CONFIG_PATH = PROJECT_ROOT / "config" / "approved_paths.yaml"
DEFAULT_LOCAL_CONFIG_PATH = PROJECT_ROOT / "config" / "default.local.yaml"
APPROVED_PATHS_LOCAL_CONFIG_PATH = PROJECT_ROOT / "config" / "approved_paths.local.yaml"


class ConfigError(RuntimeError):
    """Raised when local configuration cannot be loaded safely."""


def _read_yaml_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigError(f"Missing config file: {path}")

    try:
        with path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in config file: {path}") from exc

    if not isinstance(data, dict):
        raise ConfigError(f"Config file must contain a top-level mapping: {path}")

    return data


def _select_config_path(primary_path: Path, local_override_path: Path) -> Path:
    if local_override_path.is_file():
        return local_override_path
    return primary_path


def _resolve_configured_path(path_value: str | Path, base_dir: Path) -> Path:
    candidate = Path(path_value).expanduser()
    if not candidate.is_absolute():
        candidate = (base_dir / candidate).resolve()
    else:
        candidate = candidate.resolve()
    return candidate


def load_config() -> dict[str, Any]:
    default_config_path = _select_config_path(DEFAULT_CONFIG_PATH, DEFAULT_LOCAL_CONFIG_PATH)
    approved_paths_config_path = _select_config_path(
        APPROVED_PATHS_CONFIG_PATH,
        APPROVED_PATHS_LOCAL_CONFIG_PATH,
    )

    default_config = _read_yaml_file(default_config_path)
    approved_paths_config = _read_yaml_file(approved_paths_config_path)

    ai_brain_path = os.environ.get("AI_BRAIN_PATH", default_config.get("ai_brain_path"))
    if not ai_brain_path:
        raise ConfigError(
            "Missing ai_brain_path in config/default.yaml (or config/default.local.yaml) and AI_BRAIN_PATH is not set."
        )

    resolved_ai_brain_path = _resolve_configured_path(ai_brain_path, default_config_path.parent)
    if not resolved_ai_brain_path.exists():
        raise ConfigError(f"Configured ai_brain_path does not exist: {resolved_ai_brain_path}")

    approved_paths = approved_paths_config.get("approved_paths")
    if not isinstance(approved_paths, list):
        raise ConfigError("Config value approved_paths must be a list in config/approved_paths.yaml (or config/approved_paths.local.yaml).")

    resolved_approved_paths = [
        str(_resolve_configured_path(path, approved_paths_config_path.parent))
        for path in approved_paths
    ]

    loaded_config = dict(default_config)
    loaded_config["ai_brain_path"] = str(resolved_ai_brain_path)
    loaded_config["approved_paths"] = resolved_approved_paths

    return loaded_config
