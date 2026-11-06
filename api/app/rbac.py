"""Role-based access control: the one place permissions are decided (rule 3).

Deny by default: a role has exactly the permissions listed here and nothing else. Every route declares
the permission it needs through `require(...)` in app/deps.py; tests/test_rbac.py checks that every
route does, and checks each role against each endpoint.
"""

from enum import StrEnum


class Role(StrEnum):
    TENANT_ADMIN = "tenant_admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class Perm(StrEnum):
    TENANT_READ = "tenant:read"
    TENANTS_MANAGE = "tenants:manage"  # platform admin only: create and list all tenants
    USERS_READ = "users:read"
    USERS_MANAGE = "users:manage"
    SITES_READ = "sites:read"
    SITES_MANAGE = "sites:manage"
    CAMERAS_READ = "cameras:read"
    CAMERAS_MANAGE = "cameras:manage"
    LIVE_VIEW = "live:view"
    LIVE_VIEW_MAIN = "live:view_main"
    AUDIT_READ = "audit:read"


_VIEWER = frozenset(
    {Perm.TENANT_READ, Perm.SITES_READ, Perm.CAMERAS_READ, Perm.LIVE_VIEW, Perm.LIVE_VIEW_MAIN}
)
_OPERATOR = _VIEWER  # gains playback/export/PTZ/alert acknowledgement in M3-M4
_ADMIN = _OPERATOR | {
    Perm.USERS_READ,
    Perm.USERS_MANAGE,
    Perm.SITES_MANAGE,
    Perm.CAMERAS_MANAGE,
    Perm.AUDIT_READ,
}

ROLE_PERMISSIONS: dict[Role, frozenset[Perm]] = {
    Role.VIEWER: _VIEWER,
    Role.OPERATOR: frozenset(_OPERATOR),
    Role.TENANT_ADMIN: frozenset(_ADMIN),
}
PLATFORM_PERMISSIONS: frozenset[Perm] = frozenset({Perm.TENANTS_MANAGE})


def permissions_for(role: str | None, platform_admin: bool) -> frozenset[Perm]:
    perms: frozenset[Perm] = frozenset()
    if role is not None and role in Role.__members__.values():
        perms = ROLE_PERMISSIONS[Role(role)]
    if platform_admin:
        perms = perms | PLATFORM_PERMISSIONS
    return perms
