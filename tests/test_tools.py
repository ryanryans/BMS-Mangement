"""Test tools: table analysis, document summary, report generation, etc."""
import csv
from pathlib import Path


class TestTableAnalysisTool:
    def test_analyze_csv(self, tmp_path):
        from src.tools.table_analysis_tool import TableAnalysisTool

        # Create test CSV
        csv_path = tmp_path / "test.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["电压", "电流", "温度"])
            writer.writerow([3.7, 1.5, 25])
            writer.writerow([3.6, 1.4, 30])
            writer.writerow([3.5, 1.3, 35])

        tool = TableAnalysisTool(data_dir=tmp_path)
        result = tool.analyze("分析电池数据", str(csv_path))

        assert "电压" in result or "3.7" in result
        assert "## 表格分析结果" in result

    def test_no_file_found(self):
        from src.tools.table_analysis_tool import TableAnalysisTool
        tool = TableAnalysisTool(data_dir=Path("/nonexistent"))
        result = tool.analyze("分析一下")
        assert "未找到" in result or "表格" in result


class TestDocumentSummaryTool:
    def test_summarize_document(self):
        from src.tools.document_summary_tool import DocumentSummaryTool

        content = """
        电池管理系统(BMS)是电动汽车的核心组件。它负责监控电池的电压、电流和温度。
        BMS还需要进行电池均衡，确保每个电芯的电压保持一致。
        此外，BMS提供过充保护、过放保护和温度保护功能。
        最新的BMS系统还支持SOC(荷电状态)和SOH(健康状态)估算。
        """

        tool = DocumentSummaryTool()
        result = tool.summarize(content)

        assert result["success"]
        assert len(result["key_points"]) >= 1


class TestReportGenerationTool:
    def test_generate_standard_report(self):
        from src.tools.report_generation_tool import ReportGenerationTool

        tool = ReportGenerationTool()
        content = tool.generate("电池测试", "standard")

        assert "电池测试" in content
        assert "报告概述" in content

    def test_generate_battery_test_report(self):
        from src.tools.report_generation_tool import ReportGenerationTool

        tool = ReportGenerationTool()
        content = tool.generate("BMS单元测试", "battery_test")

        assert "BMS单元测试" in content
        assert "电压分析" in content


class TestBatteryAnalysisTool:
    def test_analyze_battery_csv(self, tmp_path):
        from src.tools.battery_data_analysis_tool import BatteryDataAnalysisTool

        csv_path = tmp_path / "battery_test.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["时间", "电压", "电流", "温度", "容量"])
            for i in range(10):
                writer.writerow([f"t{i}", 3.7 - i * 0.02, 1.5, 25 + i, 100 - i * 0.5])

        tool = BatteryDataAnalysisTool()
        result = tool.analyze("分析电池", str(csv_path))

        assert "电池" in result or "电压" in result
        assert "##" in result  # Contains markdown sections


class TestFormulaExplainTool:
    def test_explain_known_formula(self):
        from src.tools.formula_explain_tool import FormulaExplainTool

        tool = FormulaExplainTool()
        result = tool.explain("欧姆定律")

        assert "欧姆定律" in result
        assert "V = I × R" in result

    def test_explain_unknown_formula(self):
        from src.tools.formula_explain_tool import FormulaExplainTool

        tool = FormulaExplainTool()
        result = tool.explain("牛顿第二定律 F = ma")

        assert "F = ma" in result or "牛顿第二定律" in result or "公式" in result
