"""Agent middleware: tool call logging + timing."""
import time, json, logging
from typing import Callable

logger = logging.getLogger(__name__)

def log_tool_call(tool_name: str, input_args: dict, output: str, latency_ms: float):
    try:
        from src.database.sqlite_manager import get_db
        get_db().log_tool_call(tool_name=tool_name,
            input_json=json.dumps(input_args, ensure_ascii=False, default=str),
            output_json=json.dumps({"output": output[:500]}, ensure_ascii=False),
            status="success" if output and "fail" not in output.lower() else "error",
            latency_ms=int(latency_ms))
    except Exception as e:
        logger.warning("Tool log failed: %s", e)

def timing_middleware():
    class Timer:
        def __enter__(s): s.start = time.time(); s.latency_ms = 0.0; return s
        def __exit__(s, *a): s.latency_ms = (time.time() - s.start) * 1000
    return Timer()

def wrap_tool_call(tool_name: str, tool_func: Callable, **kwargs) -> tuple[str, float]:
    with timing_middleware() as timer:
        try:
            result = tool_func(**kwargs)
        except Exception as e:
            result = f"Tool error: {e}"
    log_tool_call(tool_name, kwargs, str(result), timer.latency_ms)
    return str(result), timer.latency_ms
