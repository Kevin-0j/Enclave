"""Migrations run as enclave_owner (DATABASE_URL in the migrate service), never as enclave_app."""

import asyncio
import os

from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from app.models import Base

target_metadata = Base.metadata


def _run(connection):  # type: ignore[no-untyped-def]
    context.configure(connection=connection, target_metadata=target_metadata, transaction_per_migration=True)
    with context.begin_transaction():
        context.run_migrations()


async def main() -> None:
    url = context.config.attributes.get("url") or os.environ["DATABASE_URL"]
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        await conn.run_sync(_run)
        await conn.commit()
    await engine.dispose()


asyncio.run(main())
