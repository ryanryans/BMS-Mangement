"""Test ReAct: tool parsing, LLM-driven multi-step loop."""
import pytest

class TestReActTools:
    def test_get_current_time(self):
        from src.tools.time_tools import get_current_time
        r = get_current_time(); assert ":" in r and len(r) > 10
    def test_get_city(self):
        from src.tools.time_tools import get_city
        r = get_city("Shenzhen"); assert "Shenzhen" in r
    def test_get_battery_temperature(self):
        from src.tools.battery_status_tool import get_battery_temperature
        r = get_battery_temperature(); assert "cell" in r and "C" in r

class TestMiddleware:
    def test_wrap(self):
        from src.agents.middleware import wrap_tool_call
        out, lat = wrap_tool_call("test", lambda x=1: f"r:{x}", x=42)
        assert "42" in out and lat >= 0

class TestParseToolTag:
    def test_single(self):
        from src.services.chat_service import _parse_tool_tag
        r = _parse_tool_tag('<tool name="get_current_time"/>')
        assert r and r["name"] == "get_current_time"
    def test_with_args(self):
        from src.services.chat_service import _parse_tool_tag
        r = _parse_tool_tag('<tool name="get_city">city=Harbin</tool>')
        assert r and r["name"] == "get_city" and r["args"].get("city") == "Harbin"
    def test_no_tool_in_text(self):
        from src.services.chat_service import _parse_tool_tag
        r = _parse_tool_tag("Here is your answer, no tools needed.")
        assert r is None

class TestReActRoute:
    def test_react_route(self):
        from src.agents.query_router import QueryRouter
        r = QueryRouter().route("what time is it now?")
        assert "react_tools" in r.needs_tools
    def test_chat_handle_time(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "your_deepseek_api_key_here")
        from src.models.llm_service import reset_llm; reset_llm()
        from src.services.chat_service import handle_chat
        r = handle_chat("what time is it now?")
        assert len(r["answer"]) > 5 and r["answer"] != "error"
