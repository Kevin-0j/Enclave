"""Database engine and the tenant-scoped transaction (rule 1, ADR 0001).

Every request runs in one transaction. Context GUCs are set with set_config(key, value, true), which is
transaction-local, so a pooled connection never carries one user's tenant into another request.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def engine() -> AsyncEngine:
    global _engine, _sessionmaker
    if _engine is None:
        _engine = create_async_engine(
            get_settings().database_url.get_secret_value(),
            pool_size=10,
            max_overflow=10,
            pool_pre_ping=True,
        )
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def sessionmaker() -> async_sessionmaker[AsyncSession]:
    engine()
    if _sessionmaker is None:
        raise RuntimeError("database not initialised")
    return _sessionmaker


async def dispose() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine, _sessionmaker = None, None


@dataclass(frozen=True, slots=True)
class DbContext:
    tenant_id: UUID | None = None
    user_id: UUID | None = None
    login_email: str | None = None
    refresh_hash: str | None = None
    platform_admin: bool = False


async def apply_context(session: AsyncSession, ctx: DbContext) -> None:
    values = {
        "app.tenant_id": str(ctx.tenant_id) if ctx.tenant_id else "",
        "app.user_id": str(ctx.user_id) if ctx.user_id else "",
        "app.login_email": (ctx.login_email or "").lower(),
        "app.refresh_hash": ctx.refresh_hash or "",
        "app.platform_admin": "on" if ctx.platform_admin else "",
    }
    for key, value in values.items():
        await session.execute(text("SELECT set_config(:k, :v, true)"), {"k": key, "v": value})


@asynccontextmanager
async def scoped(ctx: DbContext) -> AsyncIterator[AsyncSession]:
    """One transaction with the given RLS context. Commits on success, rolls back on error."""
    async with sessionmaker()() as session, session.begin():
        await apply_context(session, ctx)
        yield session
