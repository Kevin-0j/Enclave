"""Camera secrets (rule 4): encrypted at rest, never returned, never logged; source URL validation."""

import logging
from uuid import uuid4

import pytest
from cryptography.exceptions import InvalidTag
from sqlalchemy import text

from app import crypto
from app.config import get_settings
from app.db import DbContext, scoped
from tests.conftest import World, login

SECRET_URL = "rtsp://admin:hunter2@10.20.30.40:554/Streaming/Channels/101"


def test_envelope_round_trip_and_binding() -> None:
    t, c = uuid4(), uuid4()
    blob = crypto.seal(SECRET_URL, tenant_id=t, camera_id=c, field="main_url")
    assert b"hunter2" not in blob
    assert crypto.unseal(blob, tenant_id=t, camera_id=c, field="main_url") == SECRET_URL
    with pytest.raises(InvalidTag):  # copied to another camera, tenant or field: refuses to decrypt
        crypto.unseal(blob, tenant_id=t, camera_id=uuid4(), field="main_url")
    with pytest.raises(InvalidTag):
        crypto.unseal(blob, tenant_id=t, camera_id=c, field="sub_url")


async def test_camera_url_is_write_only(client, world: World, caplog) -> None:  # type: ignore[no-untyped-def]
    headers = await login(client, world.a.emails["tenant_admin"])
    caplog.set_level(logging.DEBUG)
    r = await client.post("/api/v1/cameras", json={"name": "Gate 2", "main_url": SECRET_URL}, headers=headers)
    assert r.status_code == 201
    cam = r.json()
    assert "hunter2" not in r.text and "url" not in " ".join(cam.keys()).replace("has_sub_stream", "")
    assert "hunter2" not in (await client.get(f"/api/v1/cameras/{cam['id']}", headers=headers)).text
    assert "hunter2" not in (await client.get("/api/v1/cameras", headers=headers)).text
    assert "hunter2" not in (await client.get("/api/v1/audit?limit=200", headers=headers)).text
    assert "hunter2" not in caplog.text
    async with scoped(DbContext(tenant_id=world.a.id)) as db:
        raw = (
            await db.execute(text("SELECT main_url_enc FROM cameras WHERE id = :i"), {"i": cam["id"]})
        ).scalar_one()
    assert b"hunter2" not in bytes(raw)


async def test_validation_errors_do_not_echo_urls(client, world: World) -> None:  # type: ignore[no-untyped-def]
    headers = await login(client, world.a.emails["tenant_admin"])
    r = await client.post("/api/v1/cameras", json={"name": "", "main_url": SECRET_URL}, headers=headers)
    assert r.status_code == 422 and "hunter2" not in r.text


async def test_private_addresses_refused_outside_dev(client, world: World, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(get_settings(), "allow_private_camera_urls", False)
    headers = await login(client, world.a.emails["tenant_admin"])
    for url in (
        "rtsp://10.0.0.8/live",
        "rtsp://127.0.0.1/live",
        "rtsp://169.254.1.1/x",
        "http://example.com/x",
    ):
        r = await client.post("/api/v1/cameras", json={"name": "x", "main_url": url}, headers=headers)
        assert r.status_code == 422, url


async def test_sim_camera_urls_cannot_be_set(client, world: World) -> None:  # type: ignore[no-untyped-def]
    headers = await login(client, world.a.emails["tenant_admin"])
    r = await client.patch(
        f"/api/v1/cameras/{world.a.cameras[1]}", json={"main_url": "rtsp://10.0.0.1/x"}, headers=headers
    )
    assert r.status_code == 422


async def test_stream_response_shape(client, world: World) -> None:  # type: ignore[no-untyped-def]
    headers = await login(client, world.a.emails["viewer"])
    r = await client.post(
        f"/api/v1/cameras/{world.a.cameras[0]}/stream", json={"variant": "sub"}, headers=headers
    )
    body = r.json()
    path = f"t/{world.a.id}/c/{world.a.cameras[0]}/sub"
    assert body["whep_url"] == f"/media/{path}/whep"
    assert body["hls_url"] == f"/hls/{path}/index.m3u8"
    assert body["variant"] == "sub" and body["token"]
