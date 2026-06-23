"""Formal FastAPI entrypoint for the enterprise knowledge-base Agent system."""

# 日志初始化必须在最前面（模块导入即执行，配置 root logger）
import src.utils.logger_handler  # noqa: F401

from src.api.app import app

__all__ = ["app"]
