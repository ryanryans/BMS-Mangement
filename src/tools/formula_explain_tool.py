"""Formula explanation tool — explains mathematical and engineering formulas."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class FormulaExplainTool:
    """Explains mathematical and engineering formulas.

    Recognizes common formula patterns and provides structured explanations.
    """

    # Common formula patterns
    KNOWN_FORMULAS = {
        "欧姆定律": {
            "formula": "V = I × R",
            "variables": {
                "V": "电压 (Voltage, 单位: V)",
                "I": "电流 (Current, 单位: A)",
                "R": "电阻 (Resistance, 单位: Ω)",
            },
            "explanation": "欧姆定律描述了电压、电流和电阻之间的关系：电压等于电流乘以电阻。",
        },
        "功率": {
            "formula": "P = V × I",
            "variables": {
                "P": "功率 (Power, 单位: W)",
                "V": "电压 (Voltage, 单位: V)",
                "I": "电流 (Current, 单位: A)",
            },
            "explanation": "功率计算公式：电功率等于电压乘以电流。",
        },
        "电池容量": {
            "formula": "C = I × t",
            "variables": {
                "C": "电池容量 (Capacity, 单位: Ah)",
                "I": "放电电流 (Discharge Current, 单位: A)",
                "t": "放电时间 (Discharge Time, 单位: h)",
            },
            "explanation": "电池容量等于放电电流乘以放电时间。这是评估电池储能能力的基本公式。",
        },
        "能量密度": {
            "formula": "E_density = E / m",
            "variables": {
                "E_density": "能量密度 (Energy Density, 单位: Wh/kg)",
                "E": "总能量 (Total Energy, 单位: Wh)",
                "m": "质量 (Mass, 单位: kg)",
            },
            "explanation": "能量密度是单位质量的电池所能储存的能量，是评估电池性能的关键指标。",
        },
    }

    def explain(self, formula_text: str) -> str:
        """Explain a formula."""
        if not formula_text or not formula_text.strip():
            return "请提供需要解释的公式。"

        # Try to match known formulas
        for name, info in self.KNOWN_FORMULAS.items():
            if name in formula_text or any(
                var in formula_text for var in info["variables"]
            ):
                return self._format_explanation(name, info)

        # Generic explanation
        return self._generic_explanation(formula_text)

    def _format_explanation(self, name: str, info: dict) -> str:
        """Format a formula explanation."""
        lines = [
            f"## {name}",
            "",
            f"**公式**: `{info['formula']}`",
            "",
            "### 变量说明",
            "",
        ]
        for var, desc in info["variables"].items():
            lines.append(f"- **{var}**: {desc}")

        lines.extend([
            "",
            "### 解释",
            "",
            info["explanation"],
        ])
        return "\n".join(lines)

    def _generic_explanation(self, formula_text: str) -> str:
        """Provide a generic formula explanation."""
        return (
            f"## 公式解释\n\n"
            f"**原始公式**: `{formula_text}`\n\n"
            "### 变量识别\n\n"
            "请提供公式中每个变量的含义和单位，系统可以给出更详细的解释。\n\n"
            "### 已识别的常见公式\n\n"
            + "\n".join(f"- {name}: `{info['formula']}`" for name, info in self.KNOWN_FORMULAS.items())
        )
