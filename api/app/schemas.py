"""Request/response models. Camera URLs are write-only: no response model has a field for them."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr

RoleName = Literal["tenant_admin", "operator", "viewer"]


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginIn(BaseModel):
    email: EmailStr
    password: SecretStr = Field(min_length=1, max_length=256)
    tenant_slug: str | None = Field(default=None, max_length=80)


class SwitchTenantIn(BaseModel):
    tenant_id: UUID


class TenantOut(Out):
    id: UUID
    name: str
    slug: str
    region: str
    retention_days: int
    status: str


class MembershipOut(BaseModel):
    tenant: TenantOut
    role: RoleName


class UserOut(Out):
    id: UUID
    email: str
    name: str
    is_platform_admin: bool


class SessionOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - OAuth token type, not a secret
    expires_in: int
    user: UserOut
    tenant: TenantOut | None
    role: RoleName | None
    permissions: list[str]
    memberships: list[MembershipOut]


class TenantCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,78}[a-z0-9]$")
    region: str = Field(default="ke-nairobi", max_length=40)
    retention_days: int = Field(default=7, ge=1, le=365)
    admin_email: EmailStr
    admin_name: str = Field(default="", max_length=200)
    admin_password: SecretStr = Field(min_length=12, max_length=256)


class MemberOut(BaseModel):
    user_id: UUID
    email: str
    name: str
    role: RoleName
    joined_at: datetime


class MemberCreateIn(BaseModel):
    email: EmailStr
    name: str = Field(default="", max_length=200)
    role: RoleName
    password: SecretStr = Field(min_length=12, max_length=256)


class MemberUpdateIn(BaseModel):
    role: RoleName


class SiteOut(Out):
    id: UUID
    name: str
    address: str
    timezone: str


class SiteCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    address: str = Field(default="", max_length=500)
    timezone: str = Field(default="Africa/Nairobi", max_length=64)


class CameraOut(Out):
    id: UUID
    name: str
    site_id: UUID | None
    source_type: Literal["sim", "rtsp", "gateway"]
    enabled: bool
    status: Literal["unknown", "online", "offline"]
    last_seen: datetime | None
    ptz_capable: bool
    has_sub_stream: bool
    created_at: datetime


class CameraCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    site_id: UUID | None = None
    source_type: Literal["rtsp"] = "rtsp"
    main_url: SecretStr = Field(max_length=2000)
    sub_url: SecretStr | None = Field(default=None, max_length=2000)


class CameraUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    site_id: UUID | None = None
    enabled: bool | None = None
    main_url: SecretStr | None = Field(default=None, max_length=2000)
    sub_url: SecretStr | None = Field(default=None, max_length=2000)


class Page[T](BaseModel):
    items: list[T]
    next_cursor: str | None = None


class StreamIn(BaseModel):
    variant: Literal["main", "sub"] = "sub"


class StreamOut(BaseModel):
    whep_url: str
    hls_url: str
    token: str
    expires_at: datetime
    variant: Literal["main", "sub"]


class AuditOut(Out):
    id: UUID
    at: datetime
    user_id: UUID | None
    action: str
    target_type: str | None
    target_id: str | None
    ip: str | None
    detail: dict[str, object]
