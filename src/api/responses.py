"""Helpers for consistent API response envelopes."""

from __future__ import annotations

from typing import Any


def success_response(message: str, data: Any | None = None) -> dict[str, Any]:
    return {
        "success": True,
        "message": message,
        "data": data,
        "error": None,
    }


def error_response(message: str, error: str, data: Any | None = None) -> dict[str, Any]:
    return {
        "success": False,
        "message": message,
        "data": data,
        "error": error,
    }
