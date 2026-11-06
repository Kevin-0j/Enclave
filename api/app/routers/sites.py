from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app import audit
from app.deps import Ctx, require
from app.models import Site
from app.rbac import Perm
from app.schemas import SiteCreateIn, SiteOut

router = APIRouter(prefix="/api/v1/sites", tags=["sites"])


@router.get("", response_model=list[SiteOut])
async def list_sites(ctx: Annotated[Ctx, Depends(require(Perm.SITES_READ))]) -> list[Site]:
    return list((await ctx.db.execute(select(Site).order_by(Site.name))).scalars())


@router.post("", response_model=SiteOut, status_code=201)
async def create_site(body: SiteCreateIn, ctx: Annotated[Ctx, Depends(require(Perm.SITES_MANAGE))]) -> Site:
    site = Site(
        id=uuid4(), tenant_id=ctx.tenant_id, name=body.name, address=body.address, timezone=body.timezone
    )
    ctx.db.add(site)
    await ctx.db.flush()
    await audit.record(
        ctx.db,
        "site.create",
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
        request=ctx.request,
        target_type="site",
        target_id=site.id,
        detail={"name": body.name},
    )
    return site
