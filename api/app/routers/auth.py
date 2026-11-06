"""Login, refresh-token rotation, logout, tenant switching and the current session.

Access tokens (15 min) travel in the Authorization header and live only in the SPA's memory. The
refresh token is an opaque random value in an HttpOnly, Secure, SameSite=Strict cookie scoped to
/api/v1/auth; only its HMAC is stored. Every refresh rotates it. Presenting an already-rotated token
revokes the whole family (theft detection).
"""

from datetime import timedelta
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.config import get_settings
from app.db import DbContext, apply_context, scoped
from app.deps import Principal, check_origin, current_principal
from app.metrics import LOGINS
from app.models import Membership, RefreshToken, Tenant, User
from app.problems import Problem
from app.ratelimit import hit
from app.rbac import permissions_for
from app.schemas import LoginIn, MembershipOut, SessionOut, SwitchTenantIn, TenantOut, UserOut
from app.security import (
    create_access_token,
    hash_password,
    hash_refresh_token,
    needs_rehash,
    new_refresh_token,
    now,
    verify_password,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
me_router = APIRouter(prefix="/api/v1", tags=["auth"])
COOKIE = "enclave_rt"
COOKIE_PATH = "/api/v1/auth"


def _set_cookie(response: Response, token: str) -> None:
    s = get_settings()
    response.set_cookie(
        COOKIE,
        token,
        max_age=s.refresh_token_days * 86400,
        path=COOKIE_PATH,
        secure=True,
        httponly=True,
        samesite="strict",
    )


def _clear_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE, path=COOKIE_PATH, secure=True, httponly=True, samesite="strict")


async def _memberships(db: AsyncSession, user_id: UUID) -> list[tuple[Membership, Tenant]]:
    rows = await db.execute(
        select(Membership, Tenant)
        .join(Tenant, Tenant.id == Membership.tenant_id)
        .where(Membership.user_id == user_id, Tenant.status == "active")
        .order_by(Tenant.name)
    )
    return [(m, t) for m, t in rows]


def _session_out(
    user: User, memberships: list[tuple[Membership, Tenant]], tenant_id: UUID | None
) -> tuple[SessionOut, UUID | None]:
    active = next(((m, t) for m, t in memberships if t.id == tenant_id), None)
    role = active[0].role if active else None
    tenant = active[1] if active else None
    token = create_access_token(
        user_id=user.id,
        tenant_id=tenant.id if tenant else None,
        role=role,
        platform_admin=user.is_platform_admin,
    )
    out = SessionOut(
        access_token=token,
        expires_in=get_settings().access_token_minutes * 60,
        user=UserOut.model_validate(user),
        tenant=TenantOut.model_validate(tenant) if tenant else None,
        role=role,
        permissions=sorted(permissions_for(role, user.is_platform_admin)),
        memberships=[MembershipOut(tenant=TenantOut.model_validate(t), role=m.role) for m, t in memberships],
    )
    return out, tenant.id if tenant else None


async def _issue_refresh(
    db: AsyncSession, user_id: UUID, tenant_id: UUID | None, family: UUID | None = None
) -> str:
    raw = new_refresh_token()
    db.add(
        RefreshToken(
            id=uuid4(),
            user_id=user_id,
            tenant_id=tenant_id,
            family_id=family or uuid4(),
            token_hash=hash_refresh_token(raw),
            expires_at=now() + timedelta(days=get_settings().refresh_token_days),
        )
    )
    await db.flush()
    return raw


@router.post("/login", response_model=SessionOut)
async def login(body: LoginIn, request: Request, response: Response) -> SessionOut:
    s = get_settings()
    email = str(body.email).lower()
    ip = audit.client_ip(request) or "unknown"
    await hit(f"login:ip:{ip}", s.login_rate_per_minute)
    await hit(f"login:email:{email}", s.login_rate_per_minute)

    failed = False
    async with scoped(DbContext(login_email=email)) as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        ok = verify_password(user.password_hash if user else None, body.password.get_secret_value())
        if not ok or user is None or not user.is_active:
            failed = True
            await audit.record(
                db, "auth.login_failed", tenant_id=None, user_id=user.id if user else None, request=request
            )
        else:
            await apply_context(db, DbContext(user_id=user.id, login_email=email))
            memberships = await _memberships(db, user.id)
            if not memberships and not user.is_platform_admin:
                raise Problem(403, "This account is not a member of any organisation.")
            chosen = next((t.id for _, t in memberships if t.slug == body.tenant_slug), None)
            if chosen is None and memberships:
                chosen = memberships[0][1].id
            out, tenant_id = _session_out(user, memberships, chosen)
            await apply_context(db, DbContext(user_id=user.id, tenant_id=tenant_id))
            if needs_rehash(user.password_hash):
                user.password_hash = hash_password(body.password.get_secret_value())
            await audit.record(db, "auth.login", tenant_id=tenant_id, user_id=user.id, request=request)
            _set_cookie(response, await _issue_refresh(db, user.id, tenant_id))
    if failed:
        LOGINS.labels(result="failed").inc()
        raise Problem(401, "That email and password don't match.")
    LOGINS.labels(result="ok").inc()
    return out


@router.post("/refresh", response_model=SessionOut, dependencies=[Depends(check_origin)])
async def refresh(request: Request, response: Response) -> SessionOut:
    raw = request.cookies.get(COOKIE)
    if not raw:
        raise Problem(401, "Sign in to continue.")
    token_hash = hash_refresh_token(raw)
    reused = False
    async with scoped(DbContext(refresh_hash=token_hash)) as db:
        row = (
            await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
        ).scalar_one_or_none()
        if row is None or row.expires_at < now():
            _clear_cookie(response)
            raise Problem(401, "Your session has expired. Sign in again.")
        await apply_context(db, DbContext(user_id=row.user_id, refresh_hash=token_hash))
        if row.revoked_at is not None:
            # A rotated token came back: someone else holds this family. Kill all of it.
            reused = True
            await db.execute(
                update(RefreshToken)
                .where(RefreshToken.family_id == row.family_id, RefreshToken.revoked_at.is_(None))
                .values(revoked_at=now())
            )
            await apply_context(db, DbContext(user_id=row.user_id, tenant_id=row.tenant_id))
            await audit.record(
                db, "auth.refresh_reuse", tenant_id=row.tenant_id, user_id=row.user_id, request=request
            )
        else:
            user = (await db.execute(select(User).where(User.id == row.user_id))).scalar_one_or_none()
            if user is None or not user.is_active:
                raise Problem(401, "Sign in to continue.")
            row.revoked_at = now()
            memberships = await _memberships(db, user.id)
            out, tenant_id = _session_out(user, memberships, row.tenant_id)
            _set_cookie(response, await _issue_refresh(db, user.id, tenant_id, row.family_id))
    if reused:
        _clear_cookie(response)
        raise Problem(401, "Your session was ended for safety. Sign in again.")
    return out


@router.post("/logout", status_code=204, dependencies=[Depends(check_origin)])
async def logout(request: Request, response: Response) -> Response:
    raw = request.cookies.get(COOKIE)
    if raw:
        token_hash = hash_refresh_token(raw)
        async with scoped(DbContext(refresh_hash=token_hash)) as db:
            row = (
                await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
            ).scalar_one_or_none()
            if row is not None:
                await apply_context(db, DbContext(user_id=row.user_id, tenant_id=row.tenant_id))
                await db.execute(
                    update(RefreshToken)
                    .where(RefreshToken.family_id == row.family_id, RefreshToken.revoked_at.is_(None))
                    .values(revoked_at=now())
                )
                await audit.record(
                    db, "auth.logout", tenant_id=row.tenant_id, user_id=row.user_id, request=request
                )
    _clear_cookie(response)
    response.status_code = 204
    return response


@router.post("/switch-tenant", response_model=SessionOut)
async def switch_tenant(
    body: SwitchTenantIn,
    request: Request,
    response: Response,
    principal: Annotated[Principal, Depends(current_principal)],
) -> SessionOut:
    async with scoped(DbContext(user_id=principal.user_id)) as db:
        user = (await db.execute(select(User).where(User.id == principal.user_id))).scalar_one()
        memberships = await _memberships(db, user.id)
        if body.tenant_id not in {t.id for _, t in memberships}:
            # Same answer whether the tenant exists or not.
            raise Problem(404, "Organisation not found.")
        out, tenant_id = _session_out(user, memberships, body.tenant_id)
        await apply_context(db, DbContext(user_id=user.id, tenant_id=tenant_id))
        await audit.record(db, "auth.switch_tenant", tenant_id=tenant_id, user_id=user.id, request=request)
        _set_cookie(response, await _issue_refresh(db, user.id, tenant_id))
    return out


@me_router.get("/me", response_model=SessionOut)
async def me(principal: Annotated[Principal, Depends(current_principal)]) -> SessionOut:
    """The caller's profile, organisations and permissions (with a fresh access token)."""
    async with scoped(DbContext(user_id=principal.user_id)) as db:
        user = (await db.execute(select(User).where(User.id == principal.user_id))).scalar_one_or_none()
        if user is None or not user.is_active:
            raise Problem(401, "Sign in to continue.")
        memberships = await _memberships(db, user.id)
    out, _ = _session_out(user, memberships, principal.tenant_id)
    return out
