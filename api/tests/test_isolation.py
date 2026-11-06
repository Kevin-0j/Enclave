"""Cross-tenant isolation suite (rule 10, NFR4). A user of tenant A must not read or act on anything
of tenant B, through any endpoint, through stream URLs, or straight through the database.

`test_every_route_is_covered` fails when a new route is added without an isolation case here.
"""

from datetime import timedelta
from uuid import UUID, uuid4

import jwt
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.db import DbContext, scoped
from app.main import app
from app.security import ALGORITHM, create_stream_token, now
from tests.conftest import World

# Every route must appear in exactly one of these. Path templates as FastAPI registers them.
COVERED = {
    ("GET", "/api/v1/cameras"),
    ("POST", "/api/v1/cameras"),
    ("GET", "/api/v1/cameras/{camera_id}"),
    ("PATCH", "/api/v1/cameras/{camera_id}"),
    ("DELETE", "/api/v1/cameras/{camera_id}"),
    ("POST", "/api/v1/cameras/{camera_id}/stream"),
    ("GET", "/api/v1/users"),
    ("POST", "/api/v1/users"),
    ("PATCH", "/api/v1/users/{user_id}"),
    ("DELETE", "/api/v1/users/{user_id}"),
    ("GET", "/api/v1/sites"),
    ("POST", "/api/v1/sites"),
    ("GET", "/api/v1/audit"),
    ("GET", "/api/v1/tenants"),
    ("POST", "/api/v1/tenants"),
    ("GET", "/api/v1/tenants/current"),
    ("POST", "/api/v1/auth/switch-tenant"),
    ("GET", "/api/v1/me"),
    ("POST", "/internal/media/auth"),
}
# No tenant data behind these (or covered in test_auth.py).
NOT_TENANT_SCOPED = {
    ("GET", "/api/v1/health"),
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/refresh"),
    ("POST", "/api/v1/auth/logout"),
    ("GET", "/api/v1/docs"),  # OpenAPI UI, disabled in production
    ("GET", "/api/v1/openapi.json"),
}


def _routes() -> set[tuple[str, str]]:
    out = set()
    for r in app.routes:
        for m in getattr(r, "methods", set()) or set():
            if m in {"HEAD", "OPTIONS"}:
                continue
            path = getattr(r, "path", "")
            if path.startswith("/api/") or path.startswith("/internal/"):
                out.add((m, path))
    return out


def test_every_route_is_covered() -> None:
    missing = _routes() - COVERED - NOT_TENANT_SCOPED
    assert not missing, f"add isolation cases for: {sorted(missing)}"


# --- Database layer -------------------------------------------------------------------------------


async def test_no_context_sees_nothing(world: World) -> None:
    async with scoped(DbContext()) as db:
        for table in (
            "tenants",
            "users",
            "memberships",
            "sites",
            "cameras",
            "camera_permissions",
            "audit_log",
        ):
            count = (await db.execute(text(f"SELECT count(*) FROM {table}"))).scalar_one()  # noqa: S608
            assert count == 0, table


async def test_tenant_context_sees_only_own_rows(world: World) -> None:
    async with scoped(DbContext(tenant_id=world.a.id)) as db:
        ids = {r[0] for r in await db.execute(text("SELECT tenant_id FROM cameras"))}
        assert ids == {world.a.id}
        sites = {r[0] for r in await db.execute(text("SELECT tenant_id FROM sites"))}
        assert sites == {world.a.id}


async def test_cannot_write_into_other_tenant(world: World) -> None:
    with pytest.raises(DBAPIError):
        async with scoped(DbContext(tenant_id=world.a.id)) as db:
            await db.execute(
                text("INSERT INTO sites (id, tenant_id, name) VALUES (:i, :t, 'x')"),
                {"i": uuid4(), "t": world.b.id},
            )


async def test_cannot_move_row_to_other_tenant(world: World) -> None:
    with pytest.raises(DBAPIError):
        async with scoped(DbContext(tenant_id=world.a.id)) as db:
            await db.execute(
                text("UPDATE cameras SET tenant_id = :b WHERE id = :c"),
                {"b": world.b.id, "c": world.a.cameras[0]},
            )


async def test_app_role_cannot_bypass_rls(world: World) -> None:
    async with scoped(DbContext()) as db:
        row = (
            await db.execute(text("SELECT rolbypassrls, rolsuper FROM pg_roles WHERE rolname = current_user"))
        ).one()
        assert row == (False, False)


async def test_audit_log_is_append_only(world: World) -> None:
    with pytest.raises(DBAPIError):
        async with scoped(DbContext(tenant_id=world.a.id)) as db:
            await db.execute(text("DELETE FROM audit_log"))
    with pytest.raises(DBAPIError):
        async with scoped(DbContext(tenant_id=world.a.id)) as db:
            await db.execute(text("UPDATE audit_log SET action = 'x'"))


async def test_tenant_admin_cannot_edit_shared_user_row(world: World) -> None:
    """users UPDATE is self-only, so an admin of A can't reset the password of someone in B."""
    async with scoped(DbContext(tenant_id=world.a.id, user_id=world.a.users["tenant_admin"])) as db:
        result = await db.execute(
            text("UPDATE users SET name = 'pwned' WHERE id = :u"), {"u": world.b.users["viewer"]}
        )
        assert result.rowcount == 0  # type: ignore[attr-defined]


# --- API layer: tenant A's admin against tenant B's data --------------------------------------------


@pytest.fixture
async def a_admin(as_role):  # type: ignore[no-untyped-def]
    return await as_role("a", "tenant_admin")


async def test_camera_endpoints_hide_other_tenant(client, a_admin, world: World) -> None:  # type: ignore[no-untyped-def]
    b_cam = world.b.cameras[0]
    listing = (await client.get("/api/v1/cameras", headers=a_admin)).json()["items"]
    listed = {c["id"] for c in listing}
    assert {str(c) for c in world.a.cameras} <= listed  # sees its own
    assert not listed & {str(c) for c in world.b.cameras}  # never B's
    assert (await client.get(f"/api/v1/cameras/{b_cam}", headers=a_admin)).status_code == 404
    assert (
        await client.patch(f"/api/v1/cameras/{b_cam}", json={"name": "x"}, headers=a_admin)
    ).status_code == 404
    assert (await client.delete(f"/api/v1/cameras/{b_cam}", headers=a_admin)).status_code == 404
    r = await client.post(f"/api/v1/cameras/{b_cam}/stream", json={"variant": "sub"}, headers=a_admin)
    assert r.status_code == 404


async def test_cannot_create_camera_in_other_tenants_site(client, a_admin, world: World) -> None:  # type: ignore[no-untyped-def]
    body = {"name": "sneaky", "site_id": str(world.b.site_id), "main_url": "rtsp://10.0.0.5/live"}
    assert (await client.post("/api/v1/cameras", json=body, headers=a_admin)).status_code == 422


async def test_user_endpoints_hide_other_tenant(client, a_admin, world: World) -> None:  # type: ignore[no-untyped-def]
    b_user = world.b.users["viewer"]
    emails = {m["email"] for m in (await client.get("/api/v1/users", headers=a_admin)).json()}
    assert set(world.a.emails.values()) <= emails
    assert not emails & set(world.b.emails.values())
    r = await client.patch(f"/api/v1/users/{b_user}", json={"role": "tenant_admin"}, headers=a_admin)
    assert r.status_code == 404
    assert (await client.delete(f"/api/v1/users/{b_user}", headers=a_admin)).status_code == 404


async def test_adding_existing_user_of_other_tenant_does_not_leak_or_change_them(  # type: ignore[no-untyped-def]
    client, a_admin, world: World
) -> None:
    """Inviting someone who already exists in B links them to A only, without touching their password."""
    body = {"email": world.b.emails["operator"], "role": "viewer", "password": "another-password-123"}
    r = await client.post("/api/v1/users", json=body, headers=a_admin)
    assert r.status_code == 201
    # B's operator still logs in with the original password and still sees B.
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": world.b.emails["operator"], "password": "another-password-123"},
    )
    assert login.status_code == 401
    # Clean up: remove the A membership again.
    await client.delete(f"/api/v1/users/{world.b.users['operator']}", headers=a_admin)


async def test_site_and_audit_endpoints_hide_other_tenant(client, a_admin, world: World, as_role) -> None:  # type: ignore[no-untyped-def]
    await as_role("b", "tenant_admin")  # creates a login audit row in B
    sites = (await client.get("/api/v1/sites", headers=a_admin)).json()
    assert {s["id"] for s in sites} == {str(world.a.site_id)}
    created = await client.post("/api/v1/sites", json={"name": "A annexe"}, headers=a_admin)
    assert created.status_code == 201
    b_admin = await as_role("b", "tenant_admin")
    assert created.json()["id"] not in {
        s["id"] for s in (await client.get("/api/v1/sites", headers=b_admin)).json()
    }
    audit = (await client.get("/api/v1/audit?limit=200", headers=a_admin)).json()
    b_users = {str(u) for u in world.b.users.values()}
    assert audit and not any(row["user_id"] in b_users for row in audit)


async def test_tenant_endpoints(client, a_admin, world: World) -> None:  # type: ignore[no-untyped-def]
    assert (await client.get("/api/v1/tenants", headers=a_admin)).status_code == 403
    body = {
        "name": "x",
        "slug": "xx-x",
        "admin_email": "x@x.enclave.demo",
        "admin_password": "a-long-password-1",
    }
    assert (await client.post("/api/v1/tenants", json=body, headers=a_admin)).status_code == 403
    current = (await client.get("/api/v1/tenants/current", headers=a_admin)).json()
    assert current["id"] == str(world.a.id)
    r = await client.post("/api/v1/auth/switch-tenant", json={"tenant_id": str(world.b.id)}, headers=a_admin)
    assert r.status_code == 404
    me = (await client.get("/api/v1/me", headers=a_admin)).json()
    assert [m["tenant"]["id"] for m in me["memberships"]] == [str(world.a.id)]


async def test_forged_access_token_with_other_tenant_is_rejected(client, world: World) -> None:  # type: ignore[no-untyped-def]
    forged = jwt.encode(
        {
            "typ": "access",
            "sub": str(world.a.users["tenant_admin"]),
            "tid": str(world.b.id),
            "role": "tenant_admin",
            "pa": False,
            "iat": now(),
            "exp": now() + timedelta(minutes=5),
        },
        "not-the-real-secret-but-long-enough-for-hs256",
        algorithm=ALGORITHM,
    )
    r = await client.get("/api/v1/cameras", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401


# --- Media layer: the MediaMTX auth hook --------------------------------------------------------------


def _path(t: UUID, c: UUID, v: str = "sub") -> str:
    return f"t/{t}/c/{c}/{v}"


def _hook(
    path: str, token: str = "", action: str = "read", protocol: str = "webrtc", **kw: str
) -> dict[str, str]:
    return {"action": action, "path": path, "protocol": protocol, "token": token, "ip": "198.51.100.4", **kw}


async def _token_for(client, headers, camera: UUID, variant: str = "sub") -> str:  # type: ignore[no-untyped-def]
    r = await client.post(f"/api/v1/cameras/{camera}/stream", json={"variant": variant}, headers=headers)
    assert r.status_code == 200, r.text
    return str(r.json()["token"])


async def test_stream_token_opens_only_its_own_path(client, media_client, a_admin, world: World) -> None:  # type: ignore[no-untyped-def]
    a_cam, a_other, b_cam = world.a.cameras[0], world.a.cameras[1], world.b.cameras[0]
    token = await _token_for(client, a_admin, a_cam)
    ok = await media_client.post("/internal/media/auth", json=_hook(_path(world.a.id, a_cam), token))
    assert ok.status_code == 200
    hls = await media_client.post(
        "/internal/media/auth", json=_hook(_path(world.a.id, a_cam), token, protocol="hls")
    )
    assert hls.status_code == 200
    for path in (
        _path(world.b.id, b_cam),  # other tenant
        _path(world.a.id, b_cam),  # other tenant's camera under our tenant prefix
        _path(world.b.id, a_cam),  # our camera under the other tenant prefix
        _path(world.a.id, a_other),  # another camera of ours
        _path(world.a.id, a_cam, "main"),  # other variant
    ):
        r = await media_client.post("/internal/media/auth", json=_hook(path, token))
        assert r.status_code == 403, path


async def test_hook_rejects_bad_tokens(media_client, world: World) -> None:  # type: ignore[no-untyped-def]
    a_cam = world.a.cameras[0]
    path = _path(world.a.id, a_cam)
    uid = world.a.users["tenant_admin"]
    expired = jwt.encode(
        {
            "typ": "stream",
            "sub": str(uid),
            "tid": str(world.a.id),
            "cid": str(a_cam),
            "var": "sub",
            "act": "read",
            "iat": now() - timedelta(minutes=5),
            "exp": now() - timedelta(minutes=4),
        },
        "test-stream-secret-0123456789abcdef01234567",
        algorithm=ALGORITHM,
    )
    forged = jwt.encode(
        {
            "typ": "stream",
            "sub": str(uid),
            "tid": str(world.a.id),
            "cid": str(a_cam),
            "var": "sub",
            "act": "read",
            "exp": now() + timedelta(minutes=1),
        },
        "wrong-secret-wrong-secret-wrong-secret-xx",
        algorithm=ALGORITHM,
    )
    access_token_as_stream = jwt.encode(
        {
            "typ": "access",
            "sub": str(uid),
            "tid": str(world.a.id),
            "cid": str(a_cam),
            "var": "sub",
            "act": "read",
            "exp": now() + timedelta(minutes=1),
        },
        "test-stream-secret-0123456789abcdef01234567",
        algorithm=ALGORITHM,
    )
    for token in ("", "garbage", expired, forged, access_token_as_stream):
        r = await media_client.post("/internal/media/auth", json=_hook(path, token))
        assert r.status_code == 403


async def test_hook_rechecks_grants_and_membership(media_client, world: World) -> None:  # type: ignore[no-untyped-def]
    """A correctly signed token is still refused if the viewer isn't granted the camera."""
    ungranted = world.a.cameras[2]
    token, _ = create_stream_token(
        user_id=world.a.users["viewer"], tenant_id=world.a.id, camera_id=ungranted, variant="sub"
    )
    r = await media_client.post("/internal/media/auth", json=_hook(_path(world.a.id, ungranted), token))
    assert r.status_code == 403
    # A B user with a validly signed token for an A camera: not a member of A.
    token, _ = create_stream_token(
        user_id=world.b.users["tenant_admin"],
        tenant_id=world.a.id,
        camera_id=world.a.cameras[0],
        variant="sub",
    )
    r = await media_client.post(
        "/internal/media/auth", json=_hook(_path(world.a.id, world.a.cameras[0]), token)
    )
    assert r.status_code == 403


async def test_hook_only_answers_the_media_network(client, world: World) -> None:  # type: ignore[no-untyped-def]
    r = await client.post("/internal/media/auth", json=_hook(_path(world.a.id, world.a.cameras[0]), "x"))
    assert r.status_code == 404


async def test_publish_rules(media_client, world: World) -> None:  # type: ignore[no-untyped-def]
    path = _path(world.a.id, world.a.cameras[0], "main")
    sim = {"user": "sim", "password": "sim-secret"}
    challenge = await media_client.post(
        "/internal/media/auth", json=_hook(path, action="publish", protocol="rtsp")
    )
    assert challenge.status_code == 401
    ok = await media_client.post(
        "/internal/media/auth", json=_hook(path, action="publish", protocol="rtsp", **sim)
    )
    assert ok.status_code == 200
    wrong = await media_client.post(
        "/internal/media/auth",
        json=_hook(path, action="publish", protocol="rtsp", user="sim", password="nope"),
    )
    assert wrong.status_code == 403
    # Simulator credentials cannot read, and publish only to paths of real sim cameras.
    read = await media_client.post("/internal/media/auth", json=_hook(path, protocol="rtsp", **sim))
    assert read.status_code == 403
    ghost = _path(world.a.id, uuid4(), "main")
    r = await media_client.post(
        "/internal/media/auth", json=_hook(ghost, action="publish", protocol="rtsp", **sim)
    )
    assert r.status_code == 403
    # A viewer's stream token cannot publish.
    token, _ = create_stream_token(
        user_id=world.a.users["viewer"], tenant_id=world.a.id, camera_id=world.a.cameras[0], variant="main"
    )
    r = await media_client.post(
        "/internal/media/auth", json=_hook(path, action="publish", protocol="rtsp", user="x", password=token)
    )
    assert r.status_code == 403


async def test_playback_and_api_are_internal_only(media_client, world: World) -> None:  # type: ignore[no-untyped-def]
    path = _path(world.a.id, world.a.cameras[0])
    token, _ = create_stream_token(
        user_id=world.a.users["tenant_admin"],
        tenant_id=world.a.id,
        camera_id=world.a.cameras[0],
        variant="sub",
    )
    for action in ("playback", "api", "metrics", "pprof"):
        r = await media_client.post("/internal/media/auth", json=_hook(path, token, action=action))
        assert r.status_code == 403, action
    internal = {"user": "enclave-api", "password": "internal-secret"}
    r = await media_client.post("/internal/media/auth", json=_hook(path, action="playback", **internal))
    assert r.status_code == 200


async def test_hook_rejects_malformed_paths(media_client, world: World) -> None:  # type: ignore[no-untyped-def]
    token, _ = create_stream_token(
        user_id=world.a.users["tenant_admin"],
        tenant_id=world.a.id,
        camera_id=world.a.cameras[0],
        variant="sub",
    )
    for path in ("", "t/x/c/y/sub", f"t/{world.a.id}/c/{world.a.cameras[0]}/sub/../main", "../etc/passwd"):
        r = await media_client.post("/internal/media/auth", json=_hook(path, token))
        assert r.status_code == 403, path
