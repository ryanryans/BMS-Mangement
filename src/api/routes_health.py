"""Health-check route for M0 service verification."""

from fastapi import APIRouter

from src.core.settings import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.service_id,
        "version": settings.version,
        "environment": settings.app_env,
    }
