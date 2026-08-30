"""Consistent API error responses."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    """Application error mapped to a consistent JSON body."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


def error_body(
    *,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"code": code, "message": message}
    if details:
        payload["details"] = details
    return {"error": payload}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(code=exc.code, message=exc.message, details=exc.details),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        _request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        code = "http_error"
        if exc.status_code == 404:
            code = "not_found"
        elif exc.status_code == 400:
            code = "bad_request"
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(code=code, message=message),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content=error_body(
                code="validation_error",
                message="Request validation failed.",
                details={"issues": exc.errors()},
            ),
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        print(f"[DEBUG] Global exception caught: {type(exc).__module__}.{type(exc).__name__}: {exc}")
        if exc.__class__.__name__ == "AppError" or (hasattr(exc, "status_code") and hasattr(exc, "code")):
            status_code = getattr(exc, "status_code", 400)
            code = getattr(exc, "code", "app_error")
            message = getattr(exc, "message", str(exc))
            details = getattr(exc, "details", None)
            return JSONResponse(
                status_code=status_code,
                content=error_body(code=code, message=message, details=details),
            )
        import logging
        logging.getLogger("app.core.errors").error("Unhandled exception: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content=error_body(code="internal_error", message=str(exc)),
        )

