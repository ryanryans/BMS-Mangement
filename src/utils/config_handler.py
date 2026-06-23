"""Configuration handler — loads YAML configs with caching."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_yaml(relative_path: str) -> dict[str, Any]:
    """Load a YAML config file relative to project root."""
    path = PROJECT_ROOT / relative_path
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_config() -> dict[str, Any]:
    """Get the main configuration."""
    return load_yaml("config/config.yaml")


def get_prompt_templates() -> dict[str, Any]:
    """Get prompt templates."""
    return load_yaml("config/prompt_templates.yaml")


def get_tool_config() -> dict[str, Any]:
    """Get tool configuration."""
    return load_yaml("config/tool_config.yaml")
