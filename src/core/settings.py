"""Environment-backed settings — explicit .env loading from project root."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

# ---- project root detection (MUST come before load_dotenv) ----
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# ---- explicit .env loading from project root ----
from dotenv import load_dotenv
_ENV_PATH = PROJECT_ROOT / ".env"
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH, override=False)


def _read_yaml(relative_path: str) -> dict:
    path = PROJECT_ROOT / relative_path
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def has_deepseek_api_key() -> bool:
    """安全检测是否有真实 DeepSeek API Key（不泄露 key 内容）。"""
    key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    return bool(key and key != "your_deepseek_api_key_here")


@dataclass(frozen=True)
class Settings:
    # ---- service identity ----
    service_id: str = "enterprise-agent-api"
    service_name: str = "Enterprise Agentic RAG Knowledge Base"
    version: str = "0.2.0"
    app_env: str = field(default_factory=lambda: _env("APP_ENV", "dev"))
    log_level: str = field(default_factory=lambda: _env("LOG_LEVEL", "INFO"))

    # ---- paths ----
    project_root: Path = PROJECT_ROOT
    env_path: Path = _ENV_PATH
    env_exists: bool = _ENV_PATH.exists()
    data_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "data")
    logs_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "logs")
    raw_documents_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "raw_documents")
    vector_db_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "vector_db")
    uploaded_images_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "uploaded_images")

    # ---- database ----
    sqlite_db_path: str = field(
        default_factory=lambda: _env("SQLITE_DB_PATH", str(PROJECT_ROOT / "data" / "app.db"))
    )

    # ---- model config (never store real key) ----
    deepseek_api_key_present: bool = field(default_factory=has_deepseek_api_key)
    chat_model_name: str = field(
        default_factory=lambda: _env("CHAT_MODEL_NAME", "deepseek-chat")
    )
    embedding_model_name: str = field(
        default_factory=lambda: _env("EMBEDDING_MODEL_NAME", "mock-embedding-v1")
    )
    deepseek_base_url: str = field(
        default_factory=lambda: _env("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    )

    # ---- RAG config ----
    rag_chunk_size: int = 400
    rag_chunk_overlap: int = 40
    rag_top_k: int = 5
    rag_similarity_threshold: float = 0.10
    rag_allowed_extensions: tuple[str, ...] = ("txt", "md", "csv", "pdf", "docx")

    # ---- memory config ----
    memory_max_items: int = 1000
    memory_importance_threshold: int = 3

    # ---- agent config ----
    agent_max_tool_calls: int = 5
    agent_planning_enabled: bool = True

    # ---- API ----
    api_prefix: str = ""

    def __post_init__(self):
        for d in [self.data_dir, self.logs_dir, self.raw_documents_dir,
                   self.vector_db_dir, self.uploaded_images_dir]:
            object.__setattr__(self, '_creating_dirs', True)
            d.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
