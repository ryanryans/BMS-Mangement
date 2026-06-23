"""统一日志配置 — 模块导入时自动初始化 root logger（控制台+文件双通道）。

所有业务代码的 logging.getLogger(__name__) 会自动继承此配置。
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

from src.core.settings import get_settings

# ---- 模块导入时自动初始化（只执行一次） ----
_initialized = False


def init_logging() -> logging.Logger:
    """初始化 root logger：控制台 INFO + 文件 DEBUG。幂等（重复调用不重复添加 handler）。"""
    global _initialized
    root = logging.getLogger()
    if _initialized:
        return root

    settings = get_settings()
    root.setLevel(logging.DEBUG)

    # 控制台 handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%H:%M:%S",
    ))
    root.addHandler(console)

    # 文件 handler — 按天轮转
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = settings.logs_dir / f"app_{datetime.now().strftime('%Y%m%d')}.log"
    file_h = logging.FileHandler(str(log_file), encoding="utf-8")
    file_h.setLevel(logging.DEBUG)
    file_h.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s",
    ))
    root.addHandler(file_h)

    _initialized = True
    logging.getLogger(__name__).info("Logging initialized: %s", log_file)
    return root


# 模块导入即初始化
init_logging()
