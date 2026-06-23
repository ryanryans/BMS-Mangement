"""Agent tool: get_battery_temperature (mock BMS data)."""
import random

def get_battery_temperature(source: str = "simulated") -> str:
    base = 40.0 + random.uniform(-3, 8)
    cells = [
        {"id": "cell_01", "temp": round(base + random.uniform(-1, 1), 1), "voltage": round(3.72 + random.uniform(-0.02, 0.02), 2), "status": "normal"},
        {"id": "cell_02", "temp": round(base + random.uniform(-1, 2), 1), "voltage": round(3.71 + random.uniform(-0.02, 0.02), 2), "status": "normal"},
        {"id": "cell_03", "temp": round(base + random.uniform(2, 5), 1), "voltage": round(3.69 + random.uniform(-0.03, 0.01), 2), "status": "warning"},
        {"id": "cell_04", "temp": round(base + random.uniform(-2, 0), 1), "voltage": round(3.73 + random.uniform(-0.01, 0.02), 2), "status": "normal"},
    ]
    temps = [c["temp"] for c in cells]
    lines = [f"[Battery Pack] Cells: {len(cells)}", f"Max: {max(temps)}C  Min: {min(temps)}C  Avg: {sum(temps)/len(temps):.1f}C  Delta: {max(temps)-min(temps):.1f}C", ""]
    for c in cells:
        icon = {"normal": "OK", "warning": "WARN", "critical": "CRIT"}.get(c["status"], "?")
        lines.append(f"  {icon} {c['id']}: {c['temp']}C | {c['voltage']}V")
    if max(temps) > 55: lines.append("CRITICAL: temp >55C, shutdown recommended!")
    elif max(temps) > 45: lines.append("WARNING: temp elevated, check cooling.")
    return "\n".join(lines)

TOOL_REGISTRY = {"get_battery_temperature": {"func": get_battery_temperature, "description": "Get real-time battery pack temp/voltage per cell with alerts.", "params": ["source"]}}

TOOL_DEFINITIONS = [{"type": "function", "function": {"name": "get_battery_temperature", "description": "Get real-time battery pack temperature per cell, voltage, and alerts.", "parameters": {"type": "object", "properties": {"source": {"type": "string", "description": "Data source, default simulated"}}, "required": []}}}]
