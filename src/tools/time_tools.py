"""Agent tools: get_current_time, get_city."""
from datetime import datetime

def get_current_time() -> str:
    now = datetime.now()
    weekdays = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    return now.strftime(f"%Y-%m-%d %H:%M:%S {weekdays[now.weekday()]}")

def get_city(city: str = "default") -> str:
    if city == "default" or not city.strip():
        city = "Shenzhen"    # Default to Shenzhen when no city specified
    return _city_info(city)

def _city_info(city: str) -> str:
    info = {
        "Shenzhen": "Shenzhen, ~28C, humidity 75%. Suitable for room-temp battery testing.",
        "Beijing": "Beijing, ~22C, humidity 40%. Watch for cold-weather battery preheating in winter.",
        "Harbin": "Harbin, ~-5C, humidity 30%. COLD: preheat battery above 10C before charging.",
    }
    return info.get(city, f"{city}: no detailed data. Use general battery management guidelines.")

TOOL_REGISTRY = {
    "get_current_time": {"func": get_current_time, "description": "Get current date/time. No params.", "params": []},
    "get_city": {"func": get_city, "description": "Get city environment info. Param: city (name).", "params": ["city"]},
}

TOOL_DEFINITIONS = [
    {"type": "function", "function": {"name": "get_current_time", "description": "Get current date and time. No parameters.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "get_city", "description": "Get city environment info (temp, humidity, battery advice).", "parameters": {"type": "object", "properties": {"city": {"type": "string", "description": "City name"}}, "required": ["city"]}}},
]
