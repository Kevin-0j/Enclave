from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from app import db, logging_setup, problems, redis_client
from app.config import get_settings
from app.routers import audit_log, auth, cameras, health, internal_media, sites, tenants, users


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await db.dispose()
    await redis_client.close()


def create_app() -> FastAPI:
    logging_setup.configure()
    s = get_settings()
    app = FastAPI(
        title="Enclave API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if s.is_production else "/api/v1/docs",
        redoc_url=None,
        openapi_url=None if s.is_production else "/api/v1/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
    )
    app.add_middleware(logging_setup.RequestIdMiddleware)
    problems.install(app)
    for r in (
        health.router,
        auth.router,
        auth.me_router,
        tenants.router,
        users.router,
        sites.router,
        cameras.router,
        audit_log.router,
        internal_media.router,
    ):
        app.include_router(r)
    # Prometheus. Never routed by Caddy; scraped on the private network.
    app.mount("/metrics", make_asgi_app())
    return app


app = create_app()
