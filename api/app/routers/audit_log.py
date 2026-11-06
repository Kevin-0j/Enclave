from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.deps import Ctx, require
from app.models import AuditLog
from app.rbac import Perm
from app.schemas import AuditOut

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get("", response_model=list[AuditOut])
async def list_audit(
    ctx: Annotated[Ctx, Depends(require(Perm.AUDIT_READ))],
    before: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[AuditOut]:
    q = select(AuditLog).order_by(AuditLog.at.desc()).limit(limit)
    if before:
        q = q.where(AuditLog.at < before)
    rows = (await ctx.db.execute(q)).scalars()
    return [
        AuditOut(
            id=r.id,
            at=r.at,
            user_id=r.user_id,
            action=r.action,
            target_type=r.target_type,
            target_id=r.target_id,
            ip=str(r.ip) if r.ip else None,
            detail=r.detail,
        )
        for r in rows
    ]
