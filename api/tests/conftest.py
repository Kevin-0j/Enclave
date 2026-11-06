"""Test fixtures. Tests run against real Postgres + Redis from compose (127.0.0.1:55432 / :56379) using
the `enclave_test` database: migrations as enclave_owner, the app as enclave_app, so RLS is real.

World: tenants A and B, each with admin / operator / viewer, a site, and three sim cameras.
Operators are granted every camera in their tenant; viewers are granted all but the last.
"""

import asyncio
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID, uuid4

import pytest


def _dotenv() -> dict[str, str]:
    env: dict[str, str] = {}
    path = Path(__file__).resolve().parents[2] / ".env"
    if path.exists():
        for line in path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


_env = _dotenv()
OWNER_URL = os.environ.get(
    "TEST_OWNER_DATABASE_URL",
    f"postgresql+asyncpg://enclave_owner:{_env.get('ENCLAVE_OWNER_PASSWORD', '')}@127.0.0.1:55432/enclave_test",
)
os.environ.setdefault(
    "DATABASE_URL",
    f"postgresql+asyncpg://enclave_app:{_env.get('ENCLAVE_APP_PASSWORD', '')}@127.0.0.1:55432/enclave_test",
)
os.environ.setdefault("REDIS_URL", f"redis://:{_env.get('REDIS_PASSWORD', '')}@127.0.0.1:56379/15")
for key, value in {
    "JWT_SECRET": "test-jwt-secret-0123456789abcdef0123456789",
    "STREAM_TOKEN_SECRET": "test-stream-secret-0123456789abcdef01234567",
    "REFRESH_PEPPER": "test-pepper",
    "CAMERA_KEK_B64": "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
    "SIM_PUBLISH_PASS": "sim-secret",
    "MEDIA_INTERNAL_PASS": "internal-secret",
    "MEDIA_HOOK_ALLOWED_CIDRS": "172.31.250.0/24",
    "LOGIN_RATE_PER_MINUTE": "1000",
    "STREAM_RATE_PER_MINUTE": "1000",
    "ALLOW_PRIVATE_CAMERA_URLS": "true",
    "APP_ORIGIN": "https://enclave.localhost",
    "ENVIRONMENT": "test",
}.items():
    os.environ[key] = value

import httpx  # noqa: E402
from alembic.config import Config  # noqa: E402

from alembic import command  # noqa: E402
from app.db import DbContext, apply_context, dispose, scoped  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Camera, CameraPermission, MediaNode, Membership, Site, Tenant, User  # noqa: E402
from app.redis_client import close as close_redis  # noqa: E402
from app.redis_client import redis  # noqa: E402
from app.security import hash_password  # noqa: E402

PASSWORD = "correct-horse-battery-staple"
ORIGIN = "https://enclave.localhost"
MEDIA_IP = "172.31.250.10"
NODE_ID = UUID("00000000-0000-4000-8000-0000000000aa")


@dataclass
class TenantWorld:
    id: UUID
    slug: str
    site_id: UUID
    cameras: list[UUID]
    users: dict[str, UUID] = field(default_factory=dict)  # role -> user id
    emails: dict[str, str] = field(default_factory=dict)


@dataclass
class World:
    a: TenantWorld
    b: TenantWorld
    platform_email: str


def _migrate() -> None:
    # The dev SSD is exFAT; macOS litters it with AppleDouble "._*" files that Alembic would try to load.
    for junk in (Path(__file__).resolve().parents[1] / "alembic").rglob("._*"):
        junk.unlink(missing_ok=True)
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    cfg.attributes["url"] = OWNER_URL
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


async def _make_tenant(label: str, pw: str) -> TenantWorld:
    tid = uuid4()
    world = TenantWorld(id=tid, slug=f"tenant-{label}", site_id=uuid4(), cameras=[uuid4() for _ in range(3)])
    async with scoped(DbContext(platform_admin=True, tenant_id=tid)) as db:
        db.add(Tenant(id=tid, name=f"Tenant {label.upper()}", slug=world.slug))
        await db.flush()
        for role in ("tenant_admin", "operator", "viewer"):
            uid = uuid4()
            email = f"{role}@{label}.enclave.demo"
            # Same context the API uses when it creates an account (INSERT ... RETURNING must be visible).
            await apply_context(db, DbContext(platform_admin=True, tenant_id=tid, login_email=email))
            db.add(User(id=uid, email=email, name=f"{role} {label}", password_hash=pw))
            await db.flush()
            db.add(Membership(user_id=uid, tenant_id=tid, role=role))
            world.users[role], world.emails[role] = uid, email
        db.add(Site(id=world.site_id, tenant_id=tid, name=f"Site {label}"))
        await db.flush()
        for i, cid in enumerate(world.cameras):
            db.add(
                Camera(
                    id=cid,
                    tenant_id=tid,
                    site_id=world.site_id,
                    media_node_id=NODE_ID,
                    name=f"Cam {label}{i}",
                    source_type="sim",
                )
            )
            await db.flush()
            db.add(CameraPermission(tenant_id=tid, camera_id=cid, user_id=world.users["operator"]))
            if i < 2:
                db.add(CameraPermission(tenant_id=tid, camera_id=cid, user_id=world.users["viewer"]))
    return world


@pytest.fixture(scope="session")
async def world() -> AsyncIterator[World]:
    await asyncio.to_thread(_migrate)  # alembic's env.py runs its own event loop
    pw = hash_password(PASSWORD)
    async with scoped(DbContext(platform_admin=True)) as db:
        db.add(
            MediaNode(
                id=NODE_ID,
                name="test-node",
                region="ke-nairobi",
                webrtc_base_url="/media",
                hls_base_url="/hls",
                internal_api_url="http://127.0.0.1:9",
            )
        )
        await apply_context(db, DbContext(platform_admin=True, login_email="platform@enclave.demo"))
        db.add(
            User(
                id=uuid4(),
                email="platform@enclave.demo",
                name="Platform",
                password_hash=pw,
                is_platform_admin=True,
            )
        )
    a = await _make_tenant("a", pw)
    b = await _make_tenant("b", pw)
    yield World(a=a, b=b, platform_email="platform@enclave.demo")
    await dispose()
    await close_redis()


@pytest.fixture(autouse=True)
async def _fresh_rate_limits() -> None:
    await redis().flushdb()


def make_client(ip: str = "203.0.113.7") -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app, client=(ip, 51234))
    return httpx.AsyncClient(
        transport=transport, base_url="https://enclave.localhost", headers={"Origin": ORIGIN}
    )


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    async with make_client() as c:
        yield c


@pytest.fixture
async def media_client() -> AsyncIterator[httpx.AsyncClient]:
    """Calls arriving from the MediaMTX address on the private media network."""
    async with make_client(MEDIA_IP) as c:
        yield c


async def login(client: httpx.AsyncClient, email: str) -> dict[str, str]:
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
async def as_role(world: World, client: httpx.AsyncClient):  # type: ignore[no-untyped-def]
    async def _as(tenant: str, role: str) -> dict[str, str]:
        tw = world.a if tenant == "a" else world.b
        return await login(client, tw.emails[role])

    return _as
