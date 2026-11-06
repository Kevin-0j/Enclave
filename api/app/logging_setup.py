"""JSON logs with request IDs, and a redaction filter so stream URLs and credentials never reach logs."""

import json
import logging
import re
import sys
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime

from starlette.types import ASGIApp, Message, Receive, Scope, Send

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

_SECRET_PATTERNS = [
    re.compile(r"(rtsps?|srt|rtmp)://[^\s'\"]+", re.I),
    re.compile(r"(Bearer\s+)[A-Za-z0-9._~+/=-]+", re.I),
    re.compile(r"(token=)[^&\s'\"]+", re.I),
]


def redact(text: str) -> str:
    text = _SECRET_PATTERNS[0].sub(r"\1://[redacted]", text)
    text = _SECRET_PATTERNS[1].sub(r"\1[redacted]", text)
    return _SECRET_PATTERNS[2].sub(r"\1[redacted]", text)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": redact(record.getMessage()),
            "request_id": request_id_var.get(),
        }
        for key in ("event", "tenant_id", "user_id", "camera_id", "decision", "reason", "action", "protocol"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, default=str)


def configure() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).handlers[:] = [handler]
        logging.getLogger(name).propagate = False


class RequestIdMiddleware:
    """Takes X-Request-ID from the proxy if it looks sane, otherwise makes one; echoes it back."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        incoming = dict(scope.get("headers") or []).get(b"x-request-id", b"").decode()
        rid = incoming if re.fullmatch(r"[A-Za-z0-9-]{8,64}", incoming) else uuid.uuid4().hex
        token = request_id_var.set(rid)

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                message.setdefault("headers", []).append((b"x-request-id", rid.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            request_id_var.reset(token)
