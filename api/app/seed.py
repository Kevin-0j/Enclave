"""Demo seed: one media node, a platform admin, and the two isolated demo tenants from
sim/cameras.json, each with an admin, an operator and a viewer. Idempotent: safe to run again.

    docker compose run --rm api python -m app.seed

Runs as the normal app role (RLS applies) with the platform-admin context, like the tenants API.
Every seeded account uses SEED_PASSWORD from the environment.
"""

import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import DbContext, apply_context, dispose, scoped
from app.models import Camera, CameraPermission, MediaNode, Membership, Site, Tenant, User
from app.security import hash_password

NODE_ID = UUID("9e8d7c6b-5a49-4382-a1b0-c9d8e7f6a501")
PLATFORM_EMAIL = "platform@enclave.demo"


async def _user(
    db: AsyncSession, email: str, name: str, password_hash: str, *, platform: bool = False
) -> User:
    await apply_context(db, DbContext(login_email=email, platform_admin=True))
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        user = User(
            id=uuid4(), email=email, name=name, password_hash=password_hash, is_platform_admin=platform
        )
        db.add(user)
        await db.flush()
    return user


async def seed() -> None:
    s = get_settings()
    if s.seed_password is None:
        sys.exit("SEED_PASSWORD is not set")
    if s.is_production:
        sys.exit("Refusing to seed demo data in production")
    pw = hash_password(s.seed_password.get_secret_value())
    config = json.loads(Path(s.cameras_json).read_text())  # noqa: ASYNC240 - one-off CLI read

    async with scoped(DbContext(platform_admin=True)) as db:
        if await db.get(MediaNode, NODE_ID) is None:
            # Relative URLs: the node is same-origin behind Caddy (and behind the Vite proxy in dev).
            db.add(
                MediaNode(
                    id=NODE_ID,
                    name="local-1",
                    region="ke-nairobi",
                    webrtc_base_url="/media",
                    hls_base_url="/hls",
                    internal_api_url=s.mediamtx_api_url,
                )
            )
        await _user(db, PLATFORM_EMAIL, "Platform admin", pw, platform=True)

    for t in config["tenants"]:
        tid = UUID(t["id"])
        async with scoped(DbContext(platform_admin=True, tenant_id=tid)) as db:
            if await db.get(Tenant, tid) is None:
                db.add(Tenant(id=tid, name=t["name"], slug=t["slug"], region="ke-nairobi", retention_days=7))
                await db.flush()
            people = {}
            prefix = t["admin_email"].split("@")[1]
            for role, local, label in (
                ("tenant_admin", "admin", "Admin"),
                ("operator", "operator", "Operator"),
                ("viewer", "viewer", "Viewer"),
            ):
                email = f"{local}@{prefix}"
                user = await _user(db, email, f"{t['name']} {label}", pw)
                await apply_context(db, DbContext(platform_admin=True, tenant_id=tid))
                if await db.get(Membership, (user.id, tid)) is None:
                    db.add(Membership(user_id=user.id, tenant_id=tid, role=role))
                people[role] = user
            site_id = UUID(t["site"]["id"])
            if await db.get(Site, site_id) is None:
                db.add(
                    Site(id=site_id, tenant_id=tid, name=t["site"]["name"], timezone=t["site"]["timezone"])
                )
            await db.flush()
            for i, c in enumerate(t["cameras"]):
                cid = UUID(c["id"])
                if await db.get(Camera, cid) is None:
                    db.add(
                        Camera(
                            id=cid,
                            tenant_id=tid,
                            site_id=site_id,
                            media_node_id=NODE_ID,
                            name=c["name"],
                            source_type="sim",
                        )
                    )
                    await db.flush()
                # Operators see every camera; the viewer is not granted the last one, to show
                # per-camera permissions in the demo.
                grants = [people["operator"]] + (
                    [people["viewer"]] if i < len(t["cameras"]) - 1 or len(t["cameras"]) < 3 else []
                )
                for u in grants:
                    if await db.get(CameraPermission, (cid, u.id)) is None:
                        db.add(CameraPermission(tenant_id=tid, camera_id=cid, user_id=u.id, can_view=True))
        print(f"seeded {t['name']}: admin/operator/viewer@{prefix}, {len(t['cameras'])} cameras")
    print(f"platform admin: {PLATFORM_EMAIL}. Password for every demo account: SEED_PASSWORD in .env")
    await dispose()


if __name__ == "__main__":
    asyncio.run(seed())
