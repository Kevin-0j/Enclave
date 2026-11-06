"""Members of the caller's tenant. Removing someone removes their membership, never the account,
because the same person may belong to another tenant."""

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select

from app import audit
from app.db import DbContext, apply_context
from app.deps import Ctx, require
from app.models import Membership, User
from app.problems import Problem
from app.rbac import Perm
from app.schemas import MemberCreateIn, MemberOut, MemberUpdateIn
from app.security import hash_password

router = APIRouter(prefix="/api/v1/users", tags=["users"])


def _member(m: Membership, u: User) -> MemberOut:
    return MemberOut(user_id=u.id, email=u.email, name=u.name, role=m.role, joined_at=m.created_at)


async def _get(ctx: Ctx, user_id: UUID) -> tuple[Membership, User]:
    row = (
        await ctx.db.execute(
            select(Membership, User)
            .join(User, User.id == Membership.user_id)
            .where(Membership.tenant_id == ctx.tenant_id, Membership.user_id == user_id)
        )
    ).first()
    if row is None:
        raise Problem(404, "Member not found.")
    return row[0], row[1]


async def _admins(ctx: Ctx) -> int:
    q = select(func.count()).where(Membership.tenant_id == ctx.tenant_id, Membership.role == "tenant_admin")
    return int((await ctx.db.execute(q)).scalar_one())


@router.get("", response_model=list[MemberOut])
async def list_members(ctx: Annotated[Ctx, Depends(require(Perm.USERS_READ))]) -> list[MemberOut]:
    rows = await ctx.db.execute(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.tenant_id == ctx.tenant_id)
        .order_by(User.email)
    )
    return [_member(m, u) for m, u in rows]


@router.post("", response_model=MemberOut, status_code=201)
async def add_member(
    body: MemberCreateIn, ctx: Annotated[Ctx, Depends(require(Perm.USERS_MANAGE))]
) -> MemberOut:
    email = str(body.email).lower()
    await apply_context(ctx.db, DbContext(tenant_id=ctx.tenant_id, user_id=ctx.user_id, login_email=email))
    user = (await ctx.db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        user = User(
            id=uuid4(),
            email=email,
            name=body.name,
            password_hash=hash_password(body.password.get_secret_value()),
        )
        ctx.db.add(user)
        await ctx.db.flush()
    elif await ctx.db.get(Membership, (user.id, ctx.tenant_id)) is not None:
        raise Problem(409, "That person is already a member.")
    membership = Membership(user_id=user.id, tenant_id=ctx.tenant_id, role=body.role)
    ctx.db.add(membership)
    await ctx.db.flush()
    await ctx.db.refresh(membership)
    await apply_context(ctx.db, DbContext(tenant_id=ctx.tenant_id, user_id=ctx.user_id))
    await audit.record(
        ctx.db,
        "member.add",
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
        request=ctx.request,
        target_type="user",
        target_id=user.id,
        detail={"role": body.role},
    )
    return _member(membership, user)


@router.patch("/{user_id}", response_model=MemberOut)
async def update_member(
    user_id: UUID, body: MemberUpdateIn, ctx: Annotated[Ctx, Depends(require(Perm.USERS_MANAGE))]
) -> MemberOut:
    membership, user = await _get(ctx, user_id)
    if membership.role == "tenant_admin" and body.role != "tenant_admin" and await _admins(ctx) <= 1:
        raise Problem(409, "An organisation needs at least one admin.")
    before = membership.role
    membership.role = body.role
    await audit.record(
        ctx.db,
        "member.role_change",
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
        request=ctx.request,
        target_type="user",
        target_id=user_id,
        detail={"from": before, "to": body.role},
    )
    return _member(membership, user)


@router.delete("/{user_id}", status_code=204)
async def remove_member(user_id: UUID, ctx: Annotated[Ctx, Depends(require(Perm.USERS_MANAGE))]) -> Response:
    if user_id == ctx.user_id:
        raise Problem(409, "You can't remove yourself.")
    membership, _ = await _get(ctx, user_id)
    if membership.role == "tenant_admin" and await _admins(ctx) <= 1:
        raise Problem(409, "An organisation needs at least one admin.")
    await ctx.db.delete(membership)
    await audit.record(
        ctx.db,
        "member.remove",
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
        request=ctx.request,
        target_type="user",
        target_id=user_id,
    )
    return Response(status_code=204)
