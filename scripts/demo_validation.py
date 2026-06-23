"""One-click validation script — clear KB → ingest demo docs → query → table → report.

Usage: python scripts/demo_validation.py
"""

import os
import sys
from pathlib import Path

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(str(PROJECT_ROOT))

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def main():
    results = {"passed": 0, "failed": 0}

    def check(condition, message):
        if condition:
            print(f"  [PASS] {message}")
            results["passed"] += 1
        else:
            print(f"  [FAIL] {message}")
            results["failed"] += 1

    def step(n, title):
        print(f"\n{'='*60}")
        print(f"  Step {n}: {title}")
        print(f"{'='*60}")

    # Step 1: Clear KB
    step(1, "Clear knowledge base")
    from src.rag.knowledge_base_service import get_kb_service, reset_kb_service
    reset_kb_service()
    kb = get_kb_service()
    clear_result = kb.clear()
    check(clear_result["success"], f"Clear OK: {clear_result['message']}")

    status = kb.get_status()
    check(status.document_count == 0, f"Document count = 0 (actual: {status.document_count})")
    check(status.chunk_count == 0, f"Chunk count = 0 (actual: {status.chunk_count})")
    check(status.vector_count == 0, f"Vector count = 0 (actual: {status.vector_count})")

    # Step 2: Ingest demo docs
    step(2, "Ingest demo documents")
    demo_dir = PROJECT_ROOT / "examples" / "demo_documents"
    files = sorted(demo_dir.glob("*"))
    print(f"  Found {len(files)} files: {[f.name for f in files]}")

    batch_result = kb.ingest_files(files)
    check(batch_result.success_count == len(files),
          f"All ingested: {batch_result.success_count}/{batch_result.total}")

    for detail in batch_result.details:
        icon = "OK" if detail.success else "FAIL"
        print(f"  [{icon}] {detail.file_name}: {detail.chunk_count} chunks | {detail.summary}")

    # Step 3: Verify status
    step(3, "Verify KB status after ingestion")
    status = kb.get_status()
    check(status.document_count >= len(files),
          f"Document count >= {len(files)} (actual: {status.document_count})")
    check(status.chunk_count > 0, f"Chunk count > 0 (actual: {status.chunk_count})")
    check(status.vector_count > 0, f"Vector count > 0 (actual: {status.vector_count})")
    check(status.status == "ready", f"Status = ready (actual: {status.status})")

    docs = kb.list_documents()
    print(f"  Documents in KB:")
    for doc in docs:
        print(f"    - {doc['doc_name']} | chunks: {doc.get('chunk_count', '?')} | status: {doc['status']}")

    # Step 4: Query "low-temp fast charge risk"
    step(4, "Query: low-temperature fast charge risk")
    answer1 = kb.query("dian wen kuai chong feng xian?")
    # Try Chinese query
    try:
        answer1 = kb.query("低温快充可能带来什么风险？")
    except Exception:
        pass
    check(answer1["evidence_count"] >= 1, f"Has evidence (actual: {answer1['evidence_count']})")
    check(answer1["confidence"] != "low", f"Confidence not low (actual: {answer1['confidence']})")

    source_files = {s["filename"] for s in answer1["sources"]}
    check("battery_knowledge.md" in source_files,
          f"Source includes battery_knowledge.md (actual: {source_files})")
    check("sweeper" not in answer1["answer"].lower() and "vacuum" not in answer1["answer"].lower(),
          "Answer does NOT contain old robot vacuum content")

    # Step 5: Query price - should have low confidence or find product_params
    step(5, "Query: battery price")
    answer2 = kb.query("电池价格是多少？")
    has_price_source = any("product_params" in s["filename"] for s in answer2["sources"])
    if has_price_source:
        check(True, "Found price info from product_params.csv (acceptable)")
    else:
        check(answer2["confidence"] == "low" or answer2["evidence_count"] == 0,
              f"No price evidence -> low confidence (actual: {answer2['confidence']})")

    # Step 6: Table analysis
    step(6, "Table analysis: battery_data.csv")
    from src.tools.table_analysis_tool import TableAnalysisTool
    tool = TableAnalysisTool()
    table_result = tool.analyze("analyze battery data", str(demo_dir / "battery_data.csv"))
    check("表格分析" in table_result or "table" in table_result.lower(), "Output has table analysis section")
    check("电压" in table_result or "voltage" in table_result.lower(), "Output has voltage info")
    check(len(table_result) > 200, f"Table result is substantial (len={len(table_result)})")

    # Step 7: Report generation
    step(7, "Report generation")
    from src.tools.report_generation_tool import ReportGenerationTool
    report_tool = ReportGenerationTool()
    report_content = report_tool.generate("BMS Project Weekly", "battery_test")
    check(len(report_content) > 100, f"Report is non-empty (len={len(report_content)})")
    check("BMS Project Weekly" in report_content, "Report contains topic")
    check(len(report_content) > 200 and report_tool,
          "Report has sufficient content")

    # Step 8: Rebuild index
    step(8, "Rebuild index")
    kb.clear()
    check(kb.get_status().vector_count == 0, "After clear, vector count = 0")
    rebuild_result = kb.rebuild_index()
    check(rebuild_result["success"], f"Rebuild OK: {rebuild_result['message']}")

    # Summary
    total = results["passed"] + results["failed"]
    print(f"\n{'='*60}")
    print(f"  Validation complete: {results['passed']}/{total} passed, {results['failed']} failed")
    print(f"{'='*60}")

    if results["failed"] == 0:
        print("\n  ALL VALIDATIONS PASSED!")
        return 0
    else:
        print(f"\n  WARNING: {results['failed']} checks failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
