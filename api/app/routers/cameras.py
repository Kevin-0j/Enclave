"""Cameras CRUD and live stream tokens. Source URLs are encrypted on write and never returned."""

import base64
import binascii
import logging
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select, tuple_

from app import audit, crypto
from app.access import get_visible_camera, visible_cameras
from app.config import get_settings
from app.deps import Ctx, require
from app.media import (
    CameraUrlError,
    Variant,
    configure_pull_source,
    media_path,
    stream_urls,
    validate_source_url,
)
from app.metrics import STREAM_TOKENS
from app.models import Camera, MediaNode, Site
from app.problems import Problem
from app.ratelimit import hit
from app.rbac import Perm
from app.schemas import CameraCreateIn, CameraOut, CameraUpdateIn, Page, StreamIn, StreamOut
from app.security import create_stream_token

router = APIRouter(prefix="/api/v1/cameras", tags=["cameras"])
log = logging.getLogger("enclave.media")


def _out(c: Camera) -> CameraOut:
    return CameraOut(
        id=c.id,
        name=c.name,
        site_id=c.site_id,
        source_type=c.source_type,
        enabled=c.enabled,
        status=c.status,
        last_seen=c.last_seen,
        ptz_capable=c.ptz_capable,
        has_sub_stream=c.source_type == "sim" or c.sub_url_enc is not None,
        created_at=c.created_at,
    )


def _cursor(c: Camera) -> str:
    return base64.urlsafe_b64encode(f"{c.name}\x1f{c.id}".encode()).decode()


def _parse_cursor(cursor: str) -> tuple[str, UUID]:
    try:
        name, _, cid = base64.urlsafe_b64decode(cursor.encode()).decode().partition("\x1f")
        return name, UUID(cid)
    except (ValueError, binascii.Error) as exc:
        raise Problem(400, "Invalid cursor.") from exc


async def _place(ctx: Ctx) -> MediaNode:
    """Media placement: the first active node. A placement table per site replaces this at scale."""
    node = (
        (await ctx.db.execute(select(MediaNode).where(MediaNode.is_active).order_by(MediaNode.name)))
        .scalars()
        .first()
    )
    if node is None:
        raise Problem(409, "No media node is available.")
    return node


async def _node(ctx: Ctx, camera: Camera) -> MediaNode:
    node = await ctx.db.get(MediaNode, camera.media_node_id)
    if node is None:
        raise Problem(409, "This camera's media node is unavailable.")
    return node


async def _check_site(ctx: Ctx, site_id: UUID | None) -> None:
    if site_id is not None and await ctx.db.get(Site, site_id) is None:
        raise Problem(422, "Site not found.")


async def _validate(url: str | None) -> None:
    if url is None:
        return
    try:
        await validate_source_url(url)
    except CameraUrlError as exc:
        raise Problem(422, str(exc)) from exc


async def _sync_media(ctx: Ctx, camera: Camera) -> None:
    if camera.source_type != "rtsp":
        return
    node = await _node(ctx, camera)
    sources: tuple[tuple[Variant, bytes | None], ...] = (
        ("main", camera.main_url_enc),
        ("sub", camera.sub_url_enc),
    )
    for variant, blob in sources:
        url = None
        if blob is not None and camera.enabled:
            url = crypto.unseal(blob, tenant_id=camera.tenant_id, camera_id=camera.id, field=f"{variant}_url")
        try:
            await configure_pull_source(node, media_path(camera.tenant_id, camera.id, variant), url)
        except Exception:  # media sync is best effort; never log the URL
            log.warning("media path sync failed", extra={"camera_id": str(camera.id)})


@router.get("", response_model=Page[CameraOut])
async def list_cameras(
    ctx: Annotated[Ctx, Depends(require(Perm.CAMERAS_READ))],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: str | None = None,
) -> Page[CameraOut]:
    q = visible_cameras(ctx).order_by(Camera.name, Camera.id).limit(limit + 1)
    if cursor:
        q = q.where(tuple_(Camera.name, Camera.id) > _parse_cursor(cursor))
    rows = list((await ctx.db.execute(q)).scalars())
    more = len(rows) > limit
    rows = rows[:limit]
    return Page(items=[_out(c) for c in rows], next_cursor=_cursor(rows[-1]) if more and rows else None)


@router.post("", response_model=CameraOut, status_code=201)
async def create_camera(
    body: CameraCreateIn, ctx: Annotated[Ctx, Depends(require(Perm.CAMERAS_MANAGE))]
) -> CameraOut:
    main = body.main_url.get_secret_value()
    sub = body.sub_url.get_secret_value() if body.sub_url else None
    await _validate(main)
    await _validate(sub)
    await _check_site(ctx, body.site_id)
    node = await _place(ctx)
    cid = uuid4()
    camera = Camera(
        id=cid,
        tenant_id=ctx.tenant_id,
        site_id=body.site_id,
        media_node_id=node.id,
        name=body.name,
        source_type=body.source_type,
        main_url_enc=crypto.seal(main, tenant_id=ctx.tenant_id, camera_id=cid, field="main_url"),
        sub_url_enc=crypto.seal(sub, tenant_id=ctx.tenant_id, camera_id=cid, field="sub_url")
        if sub
        else None,
    )
    ctx.db.add(camera)
    await ctx.db.flush()
    await ctx.db.refresh(camera)
    await audit.record(
        ctx.db,
        "camera.create",
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
        request=ctx.request,
        target_type="camera",
        target_id=cid,
        detail={"name": body.name, "source_type": body.source_type},
    )
    await _sync_media(ctx, camera)
    return _out(camera)


@router.get("/{camera_id}", response_model=CameraOut)
async def get_camera(camera_id: UUID, ctx: Annotated[Ctx, Depends(require(Perm.CAMERAS_READ))]) -> CameraOut:
    return _out(await get_visible_camera(ctx, camera_id))


@router.patch("/{camera_id}", response_model=CameraOut)
async def update_camera(
    camera_id: UUID, body: CameraUpdateIn, ctx: Annotated[Ctx, Depends(require(Perm.CAMERAS_MANAGE))]
) -> CameraOut:
    camera = await get_visible_camera(ctx, camera_id)
    changed: list[str] = []
    fields = body.model_fields_set
    if body.name is not None:
        camera.name = body.name
        changed.append("name")
    if "site_id" in fields:
        await _check_site(ctx, body.site_id)
        camera.site_id = body.site_id
        changed.append("site_id")
    if body.enabled is not None:
        camera.enabled = body.enabled
        changed.append("enabled")
    for field in ("main_url", "sub_url"):
        if field not in fields:
            continue
        if camera.source_type != "rtsp":
            raise Problem(422, "This camera's stream address is managed by Enclave.")
        secret = getattr(body, field)
        value = secret.get_secret_value() if secret else None
        if field == "main_url" and value is None:
            raise Problem(422, "A main stream address is required.")
        await _validate(value)
        blob = (
            crypto.seal(value, tenant_id=camera.tenant_id, camera_id=camera.id, field=field)
            if value
            else None
        )
        setattr(camera, f"{field}_enc", blob)
        changed.append(field)  # field name only, never the value
    await ctx.db.flush()
    await ctx.db.refresh(camera)
    await audit.record(
        ctx.db,
        "camera.update",
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
        request=ctx.request,
        target_type="camera",
        target_id=camera.id,
        detail={"fields": changed},
    )
    await _sync_media(ctx, camera)
    return _out(camera)


@router.delete("/{camera_id}", status_code=204)
async def delete_camera(
    camera_id: UUID, ctx: Annotated[Ctx, Depends(require(Perm.CAMERAS_MANAGE))]
) -> Response:
    camera = await get_visible_camera(ctx, camera_id)
    camera.enabled = False
    await _sync_media(ctx, camera)
    await ctx.db.delete(camera)
    await audit.record(
        ctx.db,
        "camera.delete",
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
        request=ctx.request,
        target_type="camera",
        target_id=camera_id,
        detail={"name": camera.name},
    )
    return Response(status_code=204)


@router.post("/{camera_id}/stream", response_model=StreamOut)
async def open_stream(
    camera_id: UUID, body: StreamIn, ctx: Annotated[Ctx, Depends(require(Perm.LIVE_VIEW))]
) -> StreamOut:
    """Issue a 60 s token for one camera stream. Grids ask for `sub`; `main` only when a tile is maximised."""
    await hit(f"stream:user:{ctx.user_id}", get_settings().stream_rate_per_minute)
    if body.variant == "main" and Perm.LIVE_VIEW_MAIN not in ctx.principal.permissions:
        raise Problem(403, "Your role does not allow the full-quality stream.")
    camera = await get_visible_camera(ctx, camera_id)
    if not camera.enabled:
        raise Problem(409, "This camera is disabled.")
    variant = body.variant
    if variant == "sub" and not (camera.source_type == "sim" or camera.sub_url_enc is not None):
        variant = "main"  # camera has a single stream
    node = await _node(ctx, camera)
    token, expires = create_stream_token(
        user_id=ctx.user_id, tenant_id=camera.tenant_id, camera_id=camera.id, variant=variant
    )
    whep, hls = stream_urls(node, camera, variant)
    await audit.record(
        ctx.db,
        "live.view",
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
        request=ctx.request,
        target_type="camera",
        target_id=camera.id,
        detail={"variant": variant},
    )
    STREAM_TOKENS.labels(variant=variant).inc()
    return StreamOut(whep_url=whep, hls_url=hls, token=token, expires_at=expires, variant=variant)
