"""ORM models. The schema itself (RLS policies, grants, partitions) is owned by Alembic migrations."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, Text, func
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _id() -> Mapped[UUID]:
    return mapped_column(primary_key=True, default=uuid4)


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[UUID] = _id()
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    region: Mapped[str] = mapped_column(String(40), default="ke-nairobi")
    retention_days: Mapped[int] = mapped_column(Integer, default=7)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = _created()


class User(Base):
    __tablename__ = "users"
    id: Mapped[UUID] = _id()
    email: Mapped[str] = mapped_column(String(320), unique=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    password_hash: Mapped[str] = mapped_column(Text)
    totp_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = _created()


class Membership(Base):
    __tablename__ = "memberships"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = _created()


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id: Mapped[UUID] = _id()
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    tenant_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True
    )
    family_id: Mapped[UUID] = mapped_column()
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = _created()


class MediaNode(Base):
    __tablename__ = "media_nodes"
    id: Mapped[UUID] = _id()
    name: Mapped[str] = mapped_column(String(100))
    region: Mapped[str] = mapped_column(String(40))
    webrtc_base_url: Mapped[str] = mapped_column(Text)
    hls_base_url: Mapped[str] = mapped_column(Text)
    internal_api_url: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Site(Base):
    __tablename__ = "sites"
    id: Mapped[UUID] = _id()
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str] = mapped_column(Text, default="")
    timezone: Mapped[str] = mapped_column(String(64), default="Africa/Nairobi")
    created_at: Mapped[datetime] = _created()


class Camera(Base):
    __tablename__ = "cameras"
    id: Mapped[UUID] = _id()
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    site_id: Mapped[UUID | None] = mapped_column(ForeignKey("sites.id", ondelete="SET NULL"), nullable=True)
    gateway_id: Mapped[UUID | None] = mapped_column(nullable=True)  # FK added with gateways in M6
    media_node_id: Mapped[UUID] = mapped_column(ForeignKey("media_nodes.id"))
    name: Mapped[str] = mapped_column(String(200))
    source_type: Mapped[str] = mapped_column(String(20))  # sim | rtsp | gateway
    main_url_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    sub_url_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    onvif_profile: Mapped[str | None] = mapped_column(String(4), nullable=True)
    ptz_capable: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), default="unknown")
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CameraPermission(Base):
    __tablename__ = "camera_permissions"
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    camera_id: Mapped[UUID] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    can_view: Mapped[bool] = mapped_column(Boolean, default=True)
    can_playback: Mapped[bool] = mapped_column(Boolean, default=False)
    can_export: Mapped[bool] = mapped_column(Boolean, default=False)
    can_ptz: Mapped[bool] = mapped_column(Boolean, default=False)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True, server_default=func.now())
    tenant_id: Mapped[UUID | None] = mapped_column(nullable=True)
    user_id: Mapped[UUID | None] = mapped_column(nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    target_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
