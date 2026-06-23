"""Report generation tool — generates structured reports from data."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class ReportGenerationTool:
    """Generates structured reports using templates.

    Supports:
    - Weekly/monthly project reports
    - Test report summaries
    - Battery analysis reports
    """

    REPORT_TEMPLATES = {
        "standard": {
            "title_template": "{topic} 报告",
            "sections": [
                ("报告概述", "summary"),
                ("数据分析", "data_analysis"),
                ("关键发现", "key_findings"),
                ("建议与下一步", "recommendations"),
            ],
        },
        "weekly": {
            "title_template": "周报：{topic} ({period})",
            "sections": [
                ("本周完成", "completed"),
                ("进行中", "in_progress"),
                ("遇到的问题", "blockers"),
                ("下周计划", "next_week"),
            ],
        },
        "battery_test": {
            "title_template": "电池测试报告：{topic}",
            "sections": [
                ("测试概述", "test_overview"),
                ("电压分析", "voltage_analysis"),
                ("电流分析", "current_analysis"),
                ("温度分析", "temperature_analysis"),
                ("容量评估", "capacity_assessment"),
                ("异常检测", "anomaly_detection"),
                ("结论", "conclusion"),
            ],
        },
    }

    def generate(self, topic: str, report_type: str = "standard",
                 data: dict[str, Any] | None = None,
                 period: str | None = None) -> str:
        """Generate a report."""
        template = self.REPORT_TEMPLATES.get(report_type, self.REPORT_TEMPLATES["standard"])

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        if not period:
            period = datetime.now().strftime("%Y年%m月")

        title = template["title_template"].format(topic=topic, period=period)

        lines = [
            f"# {title}",
            "",
            f"**生成时间**: {now}",
            f"**报告类型**: {report_type}",
            f"**主题**: {topic}",
            "",
            "---",
            "",
        ]

        for section_name, section_key in template["sections"]:
            lines.append(f"## {section_name}")
            lines.append("")

            if data and section_key in data:
                content = data[section_key]
                if isinstance(content, list):
                    for item in content:
                        lines.append(f"- {item}")
                else:
                    lines.append(str(content))
            else:
                lines.append(self._placeholder_content(section_key, topic))

            lines.append("")

        lines.extend([
            "---",
            "",
            f"> 📝 报告由企业级智能研发助手自动生成 | {now}",
        ])

        return "\n".join(lines)

    def _placeholder_content(self, section_key: str, topic: str) -> str:
        """Generate placeholder content for a section."""
        placeholders = {
            "summary": f"本报告针对「{topic}」进行分析和总结。",
            "data_analysis": "数据分析部分将在上传相关数据后进行。请上传CSV或Excel文件以获得详细分析。",
            "key_findings": "关键发现将在数据分析完成后总结。",
            "recommendations": "1. 建议定期上传数据以跟踪趋势\n2. 关注异常数据点\n3. 根据历史数据优化参数",
            "completed": f"- [{topic}] 相关任务执行中",
            "in_progress": "- 数据分析中",
            "blockers": "- 暂无阻塞项",
            "next_week": "- 继续优化和迭代",
            "test_overview": f"本次测试针对「{topic}」进行。测试条件和参数请在相关文档中查看。",
            "voltage_analysis": "电压数据将在上传电池测试CSV后进行分析。",
            "current_analysis": "电流数据将在上传电池测试CSV后进行分析。",
            "temperature_analysis": "温度数据将在上传电池测试CSV后进行分析。",
            "capacity_assessment": "容量评估将在上传完整测试数据后进行。",
            "anomaly_detection": "异常检测将在数据分析时自动进行。",
            "conclusion": "结论将在完整分析后生成。请确保所有测试数据已上传。",
        }
        return placeholders.get(section_key, f"「{section_key}」相关内容待补充。")
