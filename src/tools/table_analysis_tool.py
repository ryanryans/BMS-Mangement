"""表格分析工具 — CSV/Excel 解析 + 统计 + Markdown/JSON 转换（M6多模态）。"""

from __future__ import annotations

import csv
import json
import logging
import os
from pathlib import Path
from typing import Any

from src.core.settings import get_settings

logger = logging.getLogger(__name__)


class TableAnalysisTool:
    """读取CSV/Excel表格，输出统计分析和格式化结果。

    功能:
    - CSV解析（纯Python，零依赖）
    - Excel解析（需openpyxl）
    - 数值列自动识别 + min/max/mean统计
    - Markdown表格 + JSON双格式输出
    """

    def __init__(self, data_dir: Path | None = None):
        settings = get_settings()
        self._data_dir = data_dir or settings.data_dir

    def analyze(self, query: str, file_path: str | None = None) -> str:
        """分析表格文件，自动查找或使用指定路径。"""
        if not file_path:
            file_path = self._find_table_file()                      # 自动搜索表格文件
            if not file_path:
                return "未找到可分析的表格文件。请上传CSV文件到知识库。"

        try:
            if file_path.endswith(".csv"):
                result = self._analyze_csv(file_path)
            elif file_path.endswith((".xlsx", ".xls")):
                result = self._analyze_excel(file_path)
            else:
                return f"不支持的文件格式: {file_path}"

            return self._format_result(result, query)
        except Exception as e:
            logger.error("Table analysis failed for %s: %s", file_path, e)
            return f"表格分析失败: {e}"

    def _find_table_file(self) -> str | None:
        """在data目录中搜索CSV/Excel文件。"""
        for ext in [".csv", ".xlsx", ".xls"]:
            for path in self._data_dir.rglob(f"*{ext}"):
                return str(path)
        raw_dir = get_settings().raw_documents_dir
        if raw_dir.exists():
            for ext in [".csv", ".xlsx", ".xls"]:
                for path in raw_dir.rglob(f"*{ext}"):
                    return str(path)
        return None

    def _analyze_csv(self, file_path: str) -> dict[str, Any]:
        """解析CSV并计算数值列统计。"""
        with open(file_path, "r", encoding="utf-8-sig") as f:        # utf-8-sig 处理BOM
            reader = csv.DictReader(f)
            rows = list(reader)

        if not rows:
            return {"error": "CSV file is empty"}

        columns = list(rows[0].keys())
        numeric_cols = self._find_numeric_columns(columns, rows)     # 自动识别数值列

        # 对每个数值列计算统计指标
        stats = {}
        for col in numeric_cols:
            values = []
            for row in rows:
                try:
                    v = float(row[col]) if row[col].strip() else None
                    if v is not None:
                        values.append(v)
                except (ValueError, TypeError):
                    pass
            if values:
                stats[col] = {
                    "count": len(values),
                    "min": round(min(values), 4),
                    "max": round(max(values), 4),
                    "mean": round(sum(values) / len(values), 4),
                    "missing": len(rows) - len(values),              # 缺失值计数
                }

        return {
            "file": os.path.basename(file_path),
            "row_count": len(rows),
            "column_count": len(columns),
            "columns": columns,
            "numeric_columns": numeric_cols,
            "statistics": stats,
            "sample_rows": rows[:5],                                 # 前5行样本
        }

    def _analyze_excel(self, file_path: str) -> dict[str, Any]:
        """解析Excel文件（需要openpyxl）。"""
        try:
            import openpyxl
            wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
            sheet = wb.active
            rows = []
            headers = None
            for i, row in enumerate(sheet.iter_rows(values_only=True)):
                if i == 0:
                    headers = [str(c) if c else f"col_{j}" for j, c in enumerate(row)]
                else:
                    row_dict = {headers[j]: str(c) if c else "" for j, c in enumerate(row)}
                    rows.append(row_dict)

            columns = headers or []
            numeric_cols = self._find_numeric_columns(columns, rows)

            stats = {}
            for col in numeric_cols:
                values = []
                for row in rows:
                    try:
                        v = float(row[col]) if row[col].strip() else None
                        if v is not None:
                            values.append(v)
                    except (ValueError, TypeError):
                        pass
                if values:
                    stats[col] = {
                        "count": len(values),
                        "min": round(min(values), 4),
                        "max": round(max(values), 4),
                        "mean": round(sum(values) / len(values), 4),
                    }

            return {
                "file": os.path.basename(file_path),
                "row_count": len(rows),
                "column_count": len(columns),
                "columns": columns,
                "numeric_columns": numeric_cols,
                "statistics": stats,
                "sample_rows": rows[:5],
            }
        except ImportError:
            return {"error": "openpyxl not installed. Install with: pip install openpyxl"}
        except Exception as e:
            return {"error": f"Excel analysis failed: {e}"}

    def _find_numeric_columns(self, columns: list[str],
                               rows: list[dict]) -> list[str]:
        """自动识别包含数值数据的列（抽样前20行，>50%可转为数字即判定为数值列）。"""
        numeric = []
        for col in columns:
            num_count = 0
            for row in rows[:20]:
                val = row.get(col, "").strip()
                try:
                    float(val)
                    num_count += 1
                except (ValueError, TypeError):
                    pass
            if num_count > len(rows[:20]) * 0.5:                     # 过半可转数值
                numeric.append(col)
        return numeric

    def _format_result(self, result: dict, query: str) -> str:
        """将分析结果格式化为Markdown。"""
        if "error" in result:
            return f"表格分析遇到问题: {result['error']}"

        lines = [
            f"## 表格分析结果",
            f"",
            f"**文件**: {result['file']}",
            f"**行数**: {result['row_count']}",
            f"**列数**: {result['column_count']}",
            f"**列名**: {', '.join(result['columns'])}",
            f"",
        ]

        if result.get("statistics"):
            lines.append("### 数值列统计")
            lines.append("")
            lines.append("| 列名 | 数量 | 最小值 | 最大值 | 均值 |")
            lines.append("|------|------|--------|--------|------|")
            for col, s in result["statistics"].items():
                lines.append(f"| {col} | {s['count']} | {s['min']} | {s['max']} | {s['mean']} |")
            lines.append("")

        if result.get("sample_rows"):
            lines.append("### 数据样本 (前5行)")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(result["sample_rows"], ensure_ascii=False, indent=2))
            lines.append("```")

        return "\n".join(lines)
