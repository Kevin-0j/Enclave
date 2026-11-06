"""RFC 9457 problem details for every error response."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.logging_setup import request_id_var

TITLES = {
    400: "Bad request",
    401: "Not signed in",
    403: "Not allowed",
    404: "Not found",
    409: "Conflict",
    422: "Invalid input",
    429: "Too many requests",
    500: "Server error",
}


class Problem(Exception):
    def __init__(self, status: int, detail: str, *, type_: str = "about:blank", **extra: Any) -> None:
        self.status, self.detail, self.type_, self.extra = status, detail, type_, extra


def _body(
    status: int, detail: str, instance: str, type_: str = "about:blank", **extra: Any
) -> dict[str, Any]:
    return {
        "type": type_,
        "title": TITLES.get(status, "Error"),
        "status": status,
        "detail": detail,
        "instance": instance,
        "request_id": request_id_var.get(),
        **extra,
    }


def _resp(status: int, body: dict[str, Any], headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(body, status_code=status, media_type="application/problem+json", headers=headers)


def install(app: FastAPI) -> None:
    @app.exception_handler(Problem)
    async def _problem(request: Request, exc: Problem) -> JSONResponse:
        headers = {"Retry-After": str(exc.extra["retry_after"])} if "retry_after" in exc.extra else None
        return _resp(
            exc.status, _body(exc.status, exc.detail, request.url.path, exc.type_, **exc.extra), headers
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _resp(
            exc.status_code,
            _body(exc.status_code, str(exc.detail), request.url.path),
            dict(exc.headers or {}),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Field locations and messages only; never echo submitted values (they may be camera URLs).
        errors = [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]
        return _resp(422, _body(422, "Some fields are invalid.", request.url.path, errors=errors))
