"""Login, refresh rotation with reuse detection, logout, rate limits, cookie flags."""

from app.config import get_settings
from tests.conftest import PASSWORD, World, make_client


async def test_login_sets_strict_refresh_cookie(client, world: World) -> None:  # type: ignore[no-untyped-def]
    r = await client.post(
        "/api/v1/auth/login", json={"email": world.a.emails["viewer"], "password": PASSWORD}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["tenant"]["id"] == str(world.a.id) and body["role"] == "viewer"
    cookie = r.headers["set-cookie"].lower()
    for flag in ("httponly", "secure", "samesite=strict", "path=/api/v1/auth"):
        assert flag in cookie
    assert "refresh" not in body  # never in the body


async def test_wrong_password_and_unknown_email_look_the_same(client, world: World) -> None:  # type: ignore[no-untyped-def]
    a = await client.post("/api/v1/auth/login", json={"email": world.a.emails["viewer"], "password": "nope"})
    b = await client.post(
        "/api/v1/auth/login", json={"email": "nobody@nowhere.enclave.demo", "password": "nope"}
    )
    assert a.status_code == b.status_code == 401
    assert a.json()["detail"] == b.json()["detail"]


async def test_refresh_rotates_and_detects_reuse(world: World) -> None:
    async with make_client() as c:
        await c.post("/api/v1/auth/login", json={"email": world.a.emails["operator"], "password": PASSWORD})
        first = c.cookies.get("enclave_rt")
        r1 = await c.post("/api/v1/auth/refresh")
        assert r1.status_code == 200
        second = c.cookies.get("enclave_rt")
        assert second and second != first
        # Replaying the first (already rotated) token kills the whole family...
        c.cookies.set("enclave_rt", first, domain="enclave.localhost", path="/api/v1/auth")
        assert (await c.post("/api/v1/auth/refresh")).status_code == 401
        # ...including the newest token.
        c.cookies.set("enclave_rt", second, domain="enclave.localhost", path="/api/v1/auth")
        assert (await c.post("/api/v1/auth/refresh")).status_code == 401


async def test_refresh_requires_our_origin(world: World) -> None:
    async with make_client() as c:
        await c.post("/api/v1/auth/login", json={"email": world.a.emails["operator"], "password": PASSWORD})
        r = await c.post("/api/v1/auth/refresh", headers={"Origin": "https://evil.example"})
        assert r.status_code == 403


async def test_logout_revokes(world: World) -> None:
    async with make_client() as c:
        await c.post("/api/v1/auth/login", json={"email": world.a.emails["operator"], "password": PASSWORD})
        token = c.cookies.get("enclave_rt")
        assert (await c.post("/api/v1/auth/logout")).status_code == 204
        c.cookies.set("enclave_rt", token, domain="enclave.localhost", path="/api/v1/auth")
        assert (await c.post("/api/v1/auth/refresh")).status_code == 401


async def test_login_is_rate_limited(client, world: World, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(get_settings(), "login_rate_per_minute", 3)
    codes = [
        (
            await client.post("/api/v1/auth/login", json={"email": "x@y.enclave.demo", "password": "bad"})
        ).status_code
        for _ in range(5)
    ]
    assert codes[:3] == [401, 401, 401]
    assert codes[3] == 429
    r = await client.post("/api/v1/auth/login", json={"email": "x@y.enclave.demo", "password": "bad"})
    assert "retry-after" in r.headers


async def test_stream_requests_are_rate_limited(client, world: World, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from tests.conftest import login

    headers = await login(client, world.a.emails["viewer"])
    monkeypatch.setattr(get_settings(), "stream_rate_per_minute", 2)
    url = f"/api/v1/cameras/{world.a.cameras[0]}/stream"
    codes = [(await client.post(url, json={}, headers=headers)).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


async def test_login_and_live_view_are_audited(client, world: World) -> None:  # type: ignore[no-untyped-def]
    from tests.conftest import login

    viewer = await login(client, world.a.emails["viewer"])
    await client.post(f"/api/v1/cameras/{world.a.cameras[0]}/stream", json={}, headers=viewer)
    admin = await login(client, world.a.emails["tenant_admin"])
    actions = [
        (row["action"], row["user_id"])
        for row in (await client.get("/api/v1/audit?limit=200", headers=admin)).json()
    ]
    vid = str(world.a.users["viewer"])
    assert ("auth.login", vid) in actions
    assert ("live.view", vid) in actions
