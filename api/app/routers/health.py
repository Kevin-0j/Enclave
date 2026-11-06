from fastapi import APIRouter
from sqlalchemy import text

from app.db import DbContext, scoped
from app.redis_client import redis

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    async with scoped(DbContext()) as db:
        await db.execute(text("SELECT 1"))
    await redis().ping()
    return {"status": "ok"}
