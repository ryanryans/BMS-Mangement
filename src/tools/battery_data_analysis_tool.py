"""电池数据分析工具 — 面向车企/制造业的差异化亮点（M6领域工具）。"""

from __future__ import annotations

import csv
import logging
import os
from pathlib import Path
from typing import Any

from src.core.settings import get_settings

logger = logging.getLogger(__name__)


class BatteryDataAnalysisTool:
    """电池测试数据专项分析工具。

    分析维度:
    - 电压(V): min/max/mean/std，检测异常波动（偏离均值15%）
    - 电流(A): 充放电速率统计
    - 温度(°C): max温度检测 + 超温告警（>60°C高危, >45°C关注）
    - 容量(Ah): 容量衰减率计算（首尾对比）
    - 循环数据: 多维度退化趋势

    应用场景: BMS测试、电芯循环测试、电池包质检
    """

    # CSV列名→参数名的模糊匹配表（支持中英文多种命名）
    EXPECTED_COLUMNS = {
        "voltage":     ["电压", "voltage", "v", "volt", "端电压"],
        "current":     ["电流", "current", "a", "amp", "电流值"],
        "temperature": ["温度", "temperature", "temp", "℃", "温度值"],
        "capacity":    ["容量", "capacity", "ah", "容量值"],
        "time":        ["时间", "time", "timestamp", "周期", "cycle"],
    }

    def analyze(self, query: str, file_path: str | None = None) -> str:
        """分析电池测试CSV数据，生成结构化报告。"""
        if not file_path:
            file_path = self._find_battery_file()                    # 自动搜索电池数据文件
            if not file_path:
                return "未找到电池测试数据文件。请上传包含电压、电流、温度、容量等字段的CSV文件。"

        try:
            data = self._load_csv(file_path)                         # 加载CSV
            analysis = self._analyze_battery_data(data)              # 多维分析
            return self._format_report(analysis, file_path)          # 格式化Markdown报告
        except Exception as e:
            logger.error("Battery analysis failed: %s", e)
            return f"电池数据分析失败: {e}"

    def _find_battery_file(self) -> str | None:
        """在data目录中搜索电池测试相关CSV文件。"""
        settings = get_settings()
        battery_keywords = ["电池", "battery", "测试", "test", "cycle", "充放电"]
        for search_dir in [settings.data_dir, settings.raw_documents_dir]:
            if not search_dir.exists():
                continue
            for path in search_dir.rglob("*.csv"):
                if any(kw in path.name.lower() for kw in battery_keywords):
                    return str(path)
            # 回退：检查 test_tables 目录
            test_dir = settings.data_dir / "test_tables"
            if test_dir.exists():
                for path in test_dir.rglob("*.csv"):
                    return str(path)
        return None

    def _load_csv(self, file_path: str) -> list[dict]:
        """加载CSV文件（兼容BOM头）。"""
        with open(file_path, "r", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))

    def _analyze_battery_data(self, rows: list[dict]) -> dict[str, Any]:
        """执行电池数据多维分析。"""
        if not rows:
            return {"error": "CSV文件为空"}

        columns = list(rows[0].keys())
        col_mapping = self._map_columns(columns)                     # 自动识别列名

        analysis = {
            "file_info": {
                "row_count": len(rows),
                "columns": columns,
                "mapped_columns": {k: v for k, v in col_mapping.items() if v},
            },
            "voltage": {},
            "current": {},
            "temperature": {},
            "capacity": {},
            "anomalies": [],                                         # 异常事件列表
        }

        # 逐维度分析
        if col_mapping.get("voltage"):
            analysis["voltage"] = self._analyze_numeric(rows, col_mapping["voltage"], "V")

        if col_mapping.get("current"):
            analysis["current"] = self._analyze_numeric(rows, col_mapping["current"], "A")

        if col_mapping.get("temperature"):
            temp_analysis = self._analyze_numeric(rows, col_mapping["temperature"], "°C")
            analysis["temperature"] = temp_analysis
            # 温度异常检测
            if temp_analysis.get("max", 0) > 60:
                analysis["anomalies"].append({
                    "type": "temperature_excursion",
                    "severity": "high",
                    "message": f"温度超过60°C: 最高{temp_analysis['max']}°C，可能影响电池安全。",
                })
            elif temp_analysis.get("max", 0) > 45:
                analysis["anomalies"].append({
                    "type": "temperature_elevated",
                    "severity": "medium",
                    "message": f"温度偏高: 最高{temp_analysis['max']}°C，建议检查冷却系统。",
                })

        if col_mapping.get("capacity"):
            analysis["capacity"] = self._analyze_numeric(rows, col_mapping["capacity"], "Ah")
            # 容量衰减检测：首尾值对比
            if col_mapping.get("capacity") and col_mapping.get("time"):
                cap_values = self._extract_numeric(rows, col_mapping["capacity"])
                if len(cap_values) >= 2:
                    fade = (cap_values[0] - cap_values[-1]) / cap_values[0] * 100
                    if fade > 5:
                        analysis["anomalies"].append({
                            "type": "capacity_fade",
                            "severity": "high",
                            "message": f"容量衰减: {fade:.1f}%，建议评估电池健康状态。",
                        })
                    analysis["capacity"]["fade_percent"] = round(fade, 2)

        # 电压异常检测：偏离均值15%
        if col_mapping.get("voltage"):
            v_values = self._extract_numeric(rows, col_mapping["voltage"])
            if v_values:
                v_mean = sum(v_values) / len(v_values)
                for i, v in enumerate(v_values):
                    if abs(v - v_mean) > v_mean * 0.15:
                        analysis["anomalies"].append({
                            "type": "voltage_anomaly",
                            "severity": "medium",
                            "message": f"第{i+1}行电压异常: {v}V (均值: {v_mean:.2f}V)",
                        })
                        if len(analysis["anomalies"]) > 10:          # 异常数量截断
                            break

        return analysis

    def _map_columns(self, columns: list[str]) -> dict[str, str | None]:
        """将CSV列名自动映射到标准参数名（模糊匹配）。"""
        mapping: dict[str, str | None] = {
            "voltage": None, "current": None, "temperature": None,
            "capacity": None, "time": None,
        }
        for col in columns:
            col_lower = col.lower().strip()
            for param, keywords in self.EXPECTED_COLUMNS.items():
                if any(kw in col_lower for kw in keywords):
                    mapping[param] = col
                    break
        return mapping

    def _extract_numeric(self, rows: list[dict], col: str) -> list[float]:
        """从指定列提取数值列表（跳过非数值行）。"""
        values = []
        for row in rows:
            try:
                values.append(float(row[col]))
            except (ValueError, TypeError):
                pass
        return values

    def _analyze_numeric(self, rows: list[dict], col: str,
                          unit: str) -> dict[str, Any]:
        """计算数值列的基础统计指标。"""
        values = self._extract_numeric(rows, col)
        if not values:
            return {"count": 0, "error": "No numeric values"}

        n = len(values)
        mean_val = sum(values) / n
        variance = sum((v - mean_val) ** 2 for v in values) / n     # 总体方差
        std_dev = variance ** 0.5                                    # 标准差

        return {
            "count": n,
            "unit": unit,
            "min": round(min(values), 4),
            "max": round(max(values), 4),
            "mean": round(mean_val, 4),
            "std_dev": round(std_dev, 4),
            "missing": len(rows) - n,                                # 缺失值数量
        }

    def _format_report(self, analysis: dict, file_path: str) -> str:
        """将分析结果格式化为Markdown报告。"""
        if "error" in analysis:
            return f"分析失败: {analysis['error']}"

        info = analysis["file_info"]
        lines = [
            "# 电池测试数据分析报告",
            "",
            f"**数据文件**: {os.path.basename(file_path)}",
            f"**数据行数**: {info['row_count']}",
            f"**分析维度**: {', '.join(info['mapped_columns'].keys())}",
            "",
            "---",
            "",
        ]

        # 电压分析
        if analysis.get("voltage", {}).get("count", 0) > 0:
            v = analysis["voltage"]
            lines.extend([
                "## 电压分析",
                "",
                f"| 指标 | 数值 |",
                f"|------|------|",
                f"| 最小值 | {v['min']} {v['unit']} |",
                f"| 最大值 | {v['max']} {v['unit']} |",
                f"| 平均值 | {v['mean']} {v['unit']} |",
                f"| 标准差 | {v['std_dev']} {v['unit']} |",
                f"| 有效数据 | {v['count']} 条 |",
                "",
            ])

        # 温度分析
        if analysis.get("temperature", {}).get("count", 0) > 0:
            t = analysis["temperature"]
            lines.extend([
                "## 温度分析",
                "",
                f"| 指标 | 数值 |",
                f"|------|------|",
                f"| 最小值 | {t['min']} {t['unit']} |",
                f"| 最大值 | {t['max']} {t['unit']} |",
                f"| 平均值 | {t['mean']} {t['unit']} |",
                f"| 标准差 | {t['std_dev']} {t['unit']} |",
                "",
            ])

        # 容量分析
        if analysis.get("capacity", {}).get("count", 0) > 0:
            c = analysis["capacity"]
            lines.extend([
                "## 容量分析",
                "",
                f"| 指标 | 数值 |",
                f"|------|------|",
                f"| 最小值 | {c['min']} {c['unit']} |",
                f"| 最大值 | {c['max']} {c['unit']} |",
                f"| 平均值 | {c['mean']} {c['unit']} |",
            ])
            if "fade_percent" in c:
                fade = c["fade_percent"]
                status = "🔴 严重衰减" if fade > 10 else ("🟡 轻微衰减" if fade > 5 else "🟢 正常")
                lines.append(f"| 容量衰减 | {fade}% {status} |")
            lines.append("")

        # 异常检测
        if analysis.get("anomalies"):
            lines.extend(["## 异常检测", ""])
            for a in analysis["anomalies"]:
                sev_icon = "🔴" if a["severity"] == "high" else "🟡"
                lines.append(f"- {sev_icon} [{a['type']}] {a['message']}")
            lines.append("")
        else:
            lines.extend(["## 异常检测", "", "✅ 未检测到明显异常。", ""])

        lines.extend([
            "---",
            "",
            "> 📝 报告由电池数据分析工具自动生成。建议结合测试原始数据和领域专家意见综合判断。",
        ])

        return "\n".join(lines)
