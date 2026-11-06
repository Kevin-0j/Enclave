"""RBAC (rule 3): every route declares a permission, and each role gets exactly what the matrix says."""

import pytest
from fastapi.routing import APIRoute

from app.main import app
from app.rbac import ROLE_PERMISSIONS, Perm, Role
from tests.conftest import World, login

PUBLIC = {"/api/v1/health", "/api/v1/auth/login", "/api/v1/auth/refresh", "/api/v1/auth/logout"}
AUTHENTICATED_ONLY = {"/api/v1/me", "/api/v1/auth/switch-tenant"}  # identity only, no tenant data access
INTERNAL = {"/internal/media/auth"}  # network-restricted + credential-checked, see test_isolation.py


def _declared_permission(route) -> Perm | None:  # type: ignore[no-untyped-def]
    for dep in route.dependant.dependencies:
        perm = getattr(dep.call, "required_permission", None)
        if perm is not None:
            return perm  # type: ignore[no-any-return]
    return None


def test_every_route_declares_a_permission() -> None:
    undeclared = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue  # docs, openapi.json, mounted /metrics
        path = route.path
        if not (path.startswith("/api/") or path.startswith("/internal/")):
            continue
        if path in PUBLIC | AUTHENTICATED_ONLY | INTERNAL:
            continue
        if _declared_permission(route) is None:
            undeclared.append(path)
    assert not undeclared, f"routes without require(...): {undeclared}"


def test_roles_are_nested() -> None:
    assert (
        ROLE_PERMISSIONS[Role.VIEWER]
        <= ROLE_PERMISSIONS[Role.OPERATOR]
        <= ROLE_PERMISSIONS[Role.TENANT_ADMIN]
    )
    assert all(Perm.TENANTS_MANAGE not in p for p in ROLE_PERMISSIONS.values())


# (method, path template, body, {role: expected status})
MATRIX = [
    ("GET", "/api/v1/cameras", None, {"tenant_admin": 200, "operator": 200, "viewer": 200}),
    (
        "POST",
        "/api/v1/cameras",
        {"name": "New", "main_url": "rtsp://10.1.1.1/live"},
        {"tenant_admin": 201, "operator": 403, "viewer": 403},
    ),
    (
        "PATCH",
        "/api/v1/cameras/{cam}",
        {"name": "Renamed"},
        {"tenant_admin": 200, "operator": 403, "viewer": 403},
    ),
    ("GET", "/api/v1/users", None, {"tenant_admin": 200, "operator": 403, "viewer": 403}),
    (
        "POST",
        "/api/v1/users",
        {"email": "new-{role}@a.enclave.demo", "role": "viewer", "password": "long-enough-pass-1"},
        {"tenant_admin": 201, "operator": 403, "viewer": 403},
    ),
    ("GET", "/api/v1/sites", None, {"tenant_admin": 200, "operator": 200, "viewer": 200}),
    (
        "POST",
        "/api/v1/sites",
        {"name": "Annexe {role}"},
        {"tenant_admin": 201, "operator": 403, "viewer": 403},
    ),
    ("GET", "/api/v1/audit", None, {"tenant_admin": 200, "operator": 403, "viewer": 403}),
    ("GET", "/api/v1/tenants", None, {"tenant_admin": 403, "operator": 403, "viewer": 403}),
    ("GET", "/api/v1/tenants/current", None, {"tenant_admin": 200, "operator": 200, "viewer": 200}),
    (
        "POST",
        "/api/v1/cameras/{cam}/stream",
        {"variant": "sub"},
        {"tenant_admin": 200, "operator": 200, "viewer": 200},
    ),
    (
        "POST",
        "/api/v1/cameras/{cam}/stream",
        {"variant": "main"},
        {"tenant_admin": 200, "operator": 200, "viewer": 200},
    ),
    # The last camera is not granted to the viewer: it simply doesn't exist for them.
    ("GET", "/api/v1/cameras/{ungranted}", None, {"tenant_admin": 200, "operator": 200, "viewer": 404}),
    (
        "POST",
        "/api/v1/cameras/{ungranted}/stream",
        {"variant": "sub"},
        {"tenant_admin": 200, "operator": 200, "viewer": 404},
    ),
]


@pytest.mark.parametrize("role", ["tenant_admin", "operator", "viewer"])
@pytest.mark.parametrize(("method", "path", "body", "expected"), MATRIX)
async def test_role_matrix(client, world: World, role, method, path, body, expected) -> None:  # type: ignore[no-untyped-def]
    headers = await login(client, world.a.emails[role])
    url = path.format(cam=world.a.cameras[0], ungranted=world.a.cameras[2])
    payload = (
        {k: (v.format(role=role) if isinstance(v, str) else v) for k, v in body.items()} if body else None
    )
    r = await client.request(method, url, json=payload, headers=headers)
    assert r.status_code == expected[role], r.text


async def test_viewer_list_shows_only_granted(client, world: World) -> None:  # type: ignore[no-untyped-def]
    headers = await login(client, world.a.emails["viewer"])
    ids = {c["id"] for c in (await client.get("/api/v1/cameras", headers=headers)).json()["items"]}
    assert ids == {str(c) for c in world.a.cameras[:2]}


async def test_platform_admin_manages_tenants_but_sees_no_tenant_data(client, world: World) -> None:  # type: ignore[no-untyped-def]
    headers = await login(client, world.platform_email)
    assert (await client.get("/api/v1/tenants", headers=headers)).status_code == 200
    # Without a tenant membership, tenant endpoints are closed even to the platform admin.
    assert (await client.get("/api/v1/cameras", headers=headers)).status_code == 403
    body = {
        "name": "Tenant C",
        "slug": "tenant-c",
        "admin_email": "admin@c.enclave.demo",
        "admin_password": "a-long-password-1",
    }
    r = await client.post("/api/v1/tenants", json=body, headers=headers)
    assert r.status_code == 201
    c_admin = await client.post(
        "/api/v1/auth/login", json={"email": "admin@c.enclave.demo", "password": "a-long-password-1"}
    )
    assert c_admin.json()["tenant"]["slug"] == "tenant-c"


async def test_no_token_is_401(client) -> None:  # type: ignore[no-untyped-def]
    assert (await client.get("/api/v1/cameras")).status_code == 401
    r = await client.get("/api/v1/cameras", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401
    assert r.headers["content-type"] == "application/problem+json"
