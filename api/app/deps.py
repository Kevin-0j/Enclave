"""Request dependencies: who is calling, what they may do, and the RLS-scoped database session.

Every protected route uses `require(Perm.X)`. That dependency authenticates the bearer token, checks
the permission against app/rbac.py and opens the request transaction with the caller's tenant
context. Routes never open their own sessions.
"""

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Annotated, Any
from uuid import UUID

import jwt
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import DbContext, scoped
from app.problems import Problem
from app.rbac import Perm, permissions_for
from app.security import decode_access_token


@dataclass(frozen=True, slots=True)
class Principal:
    user_id: UUID
    tenant_id: UUID | None
    role: str | None
    platform_admin: bool
    permissions: frozenset[Perm]

    def require_tenant(self) -> UUID:
        if self.tenant_id is None:
            raise Problem(403, "Choose a tenant first.")
        return self.tenant_id


def _bearer(request: Request) -> str:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise Problem(401, "Sign in to continue.")
    return token


async def current_principal(request: Request) -> Principal:
    try:
        claims = decode_access_token(_bearer(request))
    except jwt.PyJWTError as exc:
        raise Problem(401, "Your session has expired. Sign in again.") from exc
    tid = claims.get("tid")
    platform_admin = bool(claims.get("pa"))
    role = claims.get("role")
    return Principal(
        user_id=UUID(claims["sub"]),
        tenant_id=UUID(tid) if tid else None,
        role=role,
        platform_admin=platform_admin,
        permissions=permissions_for(role, platform_admin),
    )


@dataclass(slots=True)
class Ctx:
    """What a route receives: the caller and a session already scoped to the caller's tenant."""

    principal: Principal
    db: AsyncSession
    request: Request

    @property
    def tenant_id(self) -> UUID:
        return self.principal.require_tenant()

    @property
    def user_id(self) -> UUID:
        return self.principal.user_id


def require(perm: Perm) -> Callable[..., Any]:
    async def dependency(
        request: Request, principal: Annotated[Principal, Depends(current_principal)]
    ) -> AsyncIterator[Ctx]:
        if perm not in principal.permissions:
            raise Problem(403, "Your role does not allow this.")
        if perm != Perm.TENANTS_MANAGE:
            principal.require_tenant()
        ctx = DbContext(
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            platform_admin=principal.platform_admin and perm == Perm.TENANTS_MANAGE,
        )
        async with scoped(ctx) as db:
            yield Ctx(principal=principal, db=db, request=request)

    dependency.required_permission = perm  # type: ignore[attr-defined]  # read by tests/test_rbac.py
    return dependency


def check_origin(request: Request) -> None:
    """CSRF guard for cookie-authenticated endpoints (refresh, logout): the Origin must be ours."""
    from app.config import get_settings

    origin = request.headers.get("origin")
    if origin is None or origin not in get_settings().allowed_origins:
        raise Problem(403, "Request origin not allowed.")
