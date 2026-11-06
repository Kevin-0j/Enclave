from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app import audit
from app.db import DbContext, apply_context
from app.deps import Ctx, require
from app.models import Membership, Site, Tenant, User
from app.problems import Problem
from app.rbac import Perm
from app.schemas import TenantCreateIn, TenantOut
from app.security import hash_password

router = APIRouter(prefix="/api/v1/tenants", tags=["tenants"])


@router.get("", response_model=list[TenantOut])
async def list_tenants(ctx: Annotated[Ctx, Depends(require(Perm.TENANTS_MANAGE))]) -> list[Tenant]:
    return list((await ctx.db.execute(select(Tenant).order_by(Tenant.name))).scalars())


@router.post("", response_model=TenantOut, status_code=201)
async def create_tenant(
    body: TenantCreateIn, ctx: Annotated[Ctx, Depends(require(Perm.TENANTS_MANAGE))]
) -> Tenant:
    """Platform admin: create an isolated tenant with its first admin and a default site."""
    if (await ctx.db.execute(select(Tenant.id).where(Tenant.slug == body.slug))).first():
        raise Problem(409, "That slug is taken.")
    tenant = Tenant(
        id=uuid4(), name=body.name, slug=body.slug, region=body.region, retention_days=body.retention_days
    )
    ctx.db.add(tenant)
    await ctx.db.flush()
    email = str(body.admin_email).lower()
    # Act inside the new tenant for its own rows; the platform flag stays limited to the tenants table.
    await apply_context(
        ctx.db, DbContext(tenant_id=tenant.id, user_id=ctx.user_id, login_email=email, platform_admin=True)
    )
    user = (await ctx.db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        user = User(
            id=uuid4(),
            email=email,
            name=body.admin_name,
            password_hash=hash_password(body.admin_password.get_secret_value()),
        )
        ctx.db.add(user)
        await ctx.db.flush()
    ctx.db.add(Membership(user_id=user.id, tenant_id=tenant.id, role="tenant_admin"))
    ctx.db.add(Site(id=uuid4(), tenant_id=tenant.id, name=f"{body.name} (main site)"))
    await audit.record(
        ctx.db,
        "tenant.create",
        tenant_id=tenant.id,
        user_id=ctx.user_id,
        request=ctx.request,
        target_type="tenant",
        target_id=tenant.id,
        detail={"slug": body.slug},
    )
    return tenant


@router.get("/current", response_model=TenantOut)
async def current_tenant(ctx: Annotated[Ctx, Depends(require(Perm.TENANT_READ))]) -> Tenant:
    tenant = await ctx.db.get(Tenant, ctx.tenant_id)
    if tenant is None:
        raise Problem(404, "Organisation not found.")
    return tenant
