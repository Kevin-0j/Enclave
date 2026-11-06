"""Append-only audit trail (rule 5). Writes go in the request's own transaction, so an action and its
audit record commit together or not at all."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_setup import request_id_var
from app.models import AuditLog


def client_ip(request: Request | None) -> str | None:
    if request is None or request.client is None:
        return None
    # Caddy is the only proxy in front of the API; uvicorn --proxy-headers resolves X-Forwarded-For.
    return request.client.host


async def record(
    session: AsyncSession,
    action: str,
    *,
    tenant_id: UUID | None,
    user_id: UUID | None,
    request: Request | None = None,
    target_type: str | None = None,
    target_id: UUID | str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    session.add(
        AuditLog(
            id=uuid4(),
            at=datetime.now(UTC),
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id else None,
            ip=client_ip(request),
            user_agent=(request.headers.get("user-agent", "")[:400] if request else None),
            request_id=request_id_var.get(),
            detail=detail or {},
        )
    )
    await session.flush()
