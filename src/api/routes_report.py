"""Report endpoint — 统一调用 src/services/report_service.py。LLM优先，模板只作fallback。"""

from fastapi import APIRouter
from src.api.responses import success_response
from src.api.schemas import ApiResponse, ReportData, ReportRequest
from src.services.report_service import generate_report

router = APIRouter(tags=["report"])


@router.post("/report", response_model=ApiResponse)
def report(request: ReportRequest) -> dict:
    result = generate_report(
        topic=request.topic,
        report_type=getattr(request, "report_type", "standard") or "standard",
        period=getattr(request, "month", None),
    )

    status_text = "LLM生成" if result["from_llm"] else f"模板fallback: {result['fallback_reason']}"
    data = ReportData(
        report_id=f"report-{request.topic[:20]}",
        status=status_text,
        deferred=False,
        summary=result["content"][:500],
        content=result["content"],
    )
    return success_response(f"Report generated ({status_text}).", data.model_dump())
