"""Centralized error handling for the FastAPI application.

Registers exception handlers that ensure all errors follow the consistent
format defined in API_REFERENCE.md §4:
    {"detail": "...", "error_code": "...", "context": {...}}
"""

from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

_STATUS_TO_CODE: dict[int, str] = {
    400: "VALIDATION_ERROR",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    500: "INTERNAL_ERROR",
    503: "SERVICE_UNAVAILABLE",
}


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """Convert HTTPException to consistent error format."""
    error_code = _STATUS_TO_CODE.get(exc.status_code, "INTERNAL_ERROR")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "error_code": error_code,
            "context": {},
        },
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Convert Pydantic validation errors to consistent error format."""
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Request validation failed",
            "error_code": "VALIDATION_ERROR",
            "context": {"errors": exc.errors()},
        },
    )
