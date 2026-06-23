"""FastAPI application factory."""

from fastapi import FastAPI

from src.api.exception_handlers import register_exception_handlers
from src.api.routes_chat import router as chat_router
from src.api.routes_feedback import router as feedback_router
from src.api.routes_health import router as health_router
from src.api.routes_knowledge_base import router as knowledge_base_router
from src.api.routes_memory import router as memory_router
from src.api.routes_report import router as report_router
from src.api.routes_upload import router as upload_router
from src.core.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.service_name,
        version=settings.version,
        description="Enterprise Agentic RAG knowledge-base API.",
    )
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(upload_router)
    app.include_router(knowledge_base_router)
    app.include_router(memory_router)
    app.include_router(feedback_router)
    app.include_router(report_router)
    return app


app = create_app()
