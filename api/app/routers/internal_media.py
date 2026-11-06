"""MediaMTX `authMethod: http` hook (rule 2, ADR 0002). Private network only.

MediaMTX POSTs {user, password, token, ip, action, path, protocol, id, query, userAgent} for every
publish / read / playback / api / metrics request. A 2xx allows it; anything else denies. The default
answer is 403: each branch below must positively prove the caller may do exactly this.
"""

import logging
from ipaddress import ip_address
from typing import Literal
from uuid import UUID

import jwt
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.config import get_settings
from app.db import DbContext, scoped
from app.media import parse_path
from app.metrics import MEDIA_AUTH
from app.models import Camera, CameraPermission, Membership, User
from app.rbac import Role
from app.security import constant_time_equals, decode_stream_token

router = APIRouter(prefix="/internal/media", include_in_schema=False)
log = logging.getLogger("enclave.media_auth")


class AuthRequest(BaseModel):
    user: str = Field(default="", max_length=200)
    password: str = Field(default="", max_length=4096)
    token: str = Field(default="", max_length=4096)
    ip: str = Field(default="", max_length=64)
    action: Literal["publish", "read", "playback", "api", "metrics", "pprof"]
    path: str = Field(default="", max_length=300)
    protocol: str = Field(default="", max_length=16)
    id: str | None = Field(default=None, max_length=64)
    query: str = Field(default="", max_length=4096)


def _from_media_network(request: Request) -> bool:
    if request.client is None:
        return False
    try:
        peer = ip_address(request.client.host)
    except ValueError:
        return False
    return any(peer in net for net in get_settings().hook_networks)


def _is(user: str, password: str, exp_user: str, exp_pass: str) -> bool:
    # Evaluate both comparisons so timing does not reveal which half was wrong.
    a = constant_time_equals(user, exp_user)
    b = constant_time_equals(password, exp_pass)
    return a and b


def _token_from(body: AuthRequest) -> str:
    """WebRTC/HLS send `Authorization: Bearer <token>`; MediaMTX passes it as `token`. Also accept the
    token in the password slot (SRT/RTSP style)."""
    return body.token or body.password


async def _can_read(token: str, tenant_id: UUID, camera_id: UUID, variant: str) -> tuple[bool, str]:
    try:
        claims = decode_stream_token(token)
    except jwt.PyJWTError:
        return False, "bad_token"
    if claims["act"] != "read":
        return False, "wrong_action"
    if (claims["tid"], claims["cid"], claims["var"]) != (str(tenant_id), str(camera_id), variant):
        return False, "token_path_mismatch"
    user_id = UUID(claims["sub"])
    # Re-check against the database under the token's tenant: the camera must still exist and be
    # enabled, the person must still be a member, and still be granted this camera.
    async with scoped(DbContext(tenant_id=tenant_id, user_id=user_id)) as db:
        camera = await db.get(Camera, camera_id)
        if camera is None or not camera.enabled:
            return False, "camera_unavailable"
        membership = await db.get(Membership, (user_id, tenant_id))
        user = await db.get(User, user_id)
        if membership is None or user is None or not user.is_active:
            return False, "not_a_member"
        if membership.role != Role.TENANT_ADMIN:
            grant = await db.get(CameraPermission, (camera_id, user_id))
            if grant is None or not grant.can_view:
                return False, "not_granted"
    return True, "ok"


async def _can_publish(body: AuthRequest, tenant_id: UUID, camera_id: UUID) -> tuple[bool, str]:
    s = get_settings()
    if not _is(body.user, body.password, s.sim_publish_user, s.sim_publish_pass.get_secret_value()):
        return False, "bad_publisher"  # gateway credentials arrive in M6
    async with scoped(DbContext(tenant_id=tenant_id)) as db:
        camera = (
            await db.execute(select(Camera).where(Camera.id == camera_id, Camera.source_type == "sim"))
        ).scalar_one_or_none()
    if camera is None:
        return False, "not_a_sim_camera"
    return True, "ok"


@router.post("/auth")
async def media_auth(body: AuthRequest, request: Request) -> Response:
    if not _from_media_network(request):
        # Not MediaMTX. Look like nothing is here.
        return Response(status_code=404)

    s = get_settings()
    internal = _is(body.user, body.password, s.media_internal_user, s.media_internal_pass.get_secret_value())
    allowed, reason = False, "denied"
    parsed = parse_path(body.path)

    if body.action in ("api", "metrics", "playback"):
        # Only the Enclave API itself (it proxies /list and /get with audit; browsers never call these).
        allowed, reason = (internal, "internal") if internal else (False, "not_internal")
    elif body.action == "pprof":
        allowed, reason = False, "pprof_disabled"
    elif parsed is None:
        allowed, reason = False, "bad_path"
    elif body.action == "publish":
        if not body.user and not body.password:
            # RTSP clients first try without credentials and expect a 401 challenge.
            return Response(status_code=401)
        if body.protocol not in ("rtsp", "srt"):
            allowed, reason = False, "bad_protocol"
        else:
            allowed, reason = await _can_publish(body, parsed[0], parsed[1])
    elif body.action == "read":
        if internal and body.protocol == "rtsp":
            allowed, reason = True, "internal"  # motion worker reads sub-streams (M4)
        elif body.protocol not in ("webrtc", "hls"):
            allowed, reason = False, "bad_protocol"
        elif not _token_from(body):
            allowed, reason = False, "no_token"
        else:
            allowed, reason = await _can_read(_token_from(body), *parsed)

    decision = "allow" if allowed else "deny"
    MEDIA_AUTH.labels(action=body.action, decision=decision).inc()
    log.info(
        "media auth",
        extra={
            "event": "media_auth",
            "decision": decision,
            "reason": reason,
            "action": body.action,
            "protocol": body.protocol,
            "tenant_id": str(parsed[0]) if parsed else None,
            "camera_id": str(parsed[1]) if parsed else None,
        },
    )
    return Response(status_code=200 if allowed else 403)
