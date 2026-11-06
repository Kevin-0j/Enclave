"""Media paths, stream URLs and camera-source validation (rule 2, ADR 0002)."""

import asyncio
import ipaddress
import re
import socket
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

import httpx

from app.config import get_settings
from app.models import Camera, MediaNode

Variant = Literal["main", "sub"]
_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
PATH_RE = re.compile(rf"^t/(?P<tenant>{_UUID})/c/(?P<camera>{_UUID})/(?P<variant>main|sub)$")


def media_path(tenant_id: UUID, camera_id: UUID, variant: Variant) -> str:
    return f"t/{tenant_id}/c/{camera_id}/{variant}"


def parse_path(path: str) -> tuple[UUID, UUID, Variant] | None:
    m = PATH_RE.match(path)
    if not m:
        return None
    variant: Variant = "main" if m["variant"] == "main" else "sub"
    return UUID(m["tenant"]), UUID(m["camera"]), variant


def stream_urls(node: MediaNode, camera: Camera, variant: Variant) -> tuple[str, str]:
    path = media_path(camera.tenant_id, camera.id, variant)
    return (
        f"{node.webrtc_base_url.rstrip('/')}/{path}/whep",
        f"{node.hls_base_url.rstrip('/')}/{path}/index.m3u8",
    )


class CameraUrlError(ValueError):
    pass


async def validate_source_url(url: str) -> None:
    """Accept rtsp/rtsps URLs only, and (outside dev) refuse private, loopback and link-local targets so a
    tenant cannot point the cloud media node at internal services (SSRF)."""
    parts = urlsplit(url)
    if parts.scheme not in ("rtsp", "rtsps") or not parts.hostname:
        raise CameraUrlError("Use an rtsp:// or rtsps:// address.")
    if get_settings().allow_private_camera_urls:
        return
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(
            parts.hostname, parts.port or 554, type=socket.SOCK_STREAM
        )
    except socket.gaierror as exc:
        raise CameraUrlError("That camera address does not resolve.") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise CameraUrlError(
                "Cameras on a private network connect through an Enclave gateway, not a direct address."
            )


async def configure_pull_source(node: MediaNode, path: str, source_url: str | None) -> None:
    """Point a MediaMTX path at a pulled RTSP source, on demand (or remove it). Best effort: the camera
    record is the source of truth and is re-synced on the next change."""
    s = get_settings()
    auth = (s.media_internal_user, s.media_internal_pass.get_secret_value())
    base = node.internal_api_url.rstrip("/")
    async with httpx.AsyncClient(timeout=5, auth=auth) as client:
        if source_url is None:
            await client.delete(f"{base}/v3/config/paths/delete/{path}")
            return
        body = {"source": source_url, "sourceOnDemand": True, "rtspTransport": "tcp"}
        r = await client.post(f"{base}/v3/config/paths/add/{path}", json=body)
        if r.status_code == 400 and "already exists" in r.text:
            await client.patch(f"{base}/v3/config/paths/patch/{path}", json=body)
