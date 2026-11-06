"""Per-camera access within a tenant (rule 3). Tenant admins see every camera in their tenant.
Operators and viewers see only cameras they have been granted (camera_permissions.can_view):
deny by default. RLS already confines everything to the caller's tenant; this narrows it further."""

from uuid import UUID

from sqlalchemy import Select, exists, select

from app.deps import Ctx
from app.models import Camera, CameraPermission
from app.problems import Problem
from app.rbac import Role


def visible_cameras(ctx: Ctx) -> Select[Camera]:
    q = select(Camera)
    if ctx.principal.role != Role.TENANT_ADMIN:
        q = q.where(
            exists().where(
                CameraPermission.camera_id == Camera.id,
                CameraPermission.user_id == ctx.user_id,
                CameraPermission.can_view.is_(True),
            )
        )
    return q


async def get_visible_camera(ctx: Ctx, camera_id: UUID) -> Camera:
    camera = (await ctx.db.execute(visible_cameras(ctx).where(Camera.id == camera_id))).scalar_one_or_none()
    if camera is None:
        # 404 whether it belongs to another tenant, does not exist, or is not granted: no oracle.
        raise Problem(404, "Camera not found.")
    return camera
