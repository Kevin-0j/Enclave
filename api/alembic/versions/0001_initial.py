"""M1 schema: tenants, users, memberships, refresh tokens, media nodes, sites, cameras, camera
permissions and the partitioned, append-only audit log, with RLS policies (ADR 0001).

Revision ID: 0001
Revises:
"""

from datetime import date
from itertools import pairwise

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

# Default-deny helpers: an unset GUC becomes NULL, and NULL never equals anything.
TENANT = "nullif(current_setting('app.tenant_id', true), '')::uuid"
USER = "nullif(current_setting('app.user_id', true), '')::uuid"
LOGIN_EMAIL = "nullif(current_setting('app.login_email', true), '')"
REFRESH_HASH = "nullif(current_setting('app.refresh_hash', true), '')"
PLATFORM = "coalesce(current_setting('app.platform_admin', true), '') = 'on'"

TENANT_OWNED = ["sites", "cameras", "camera_permissions"]


def _run(sql: str) -> None:
    """Execute a script one statement at a time (asyncpg prepares each statement separately).
    Splits on semicolons outside $$-quoted function bodies and outside -- comments."""
    statement, in_dollar = [], False
    for line in sql.splitlines():
        if line.strip().startswith("--") and not in_dollar:
            continue
        in_dollar ^= line.count("$$") % 2 == 1
        statement.append(line)
        if not in_dollar and line.rstrip().endswith(";"):
            text = "\n".join(statement).strip()
            if text.strip(";").strip():
                op.execute(text)
            statement = []
    rest = "\n".join(statement).strip()
    if rest:
        op.execute(rest)


def _month_starts(first: date, count: int) -> list[date]:
    out, y, m = [], first.year, first.month
    for _ in range(count + 1):
        out.append(date(y, m, 1))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    _run(
        """
        CREATE TABLE tenants (
          id uuid PRIMARY KEY,
          name text NOT NULL CHECK (length(name) BETWEEN 1 AND 200),
          slug text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9][a-z0-9-]{1,78}[a-z0-9]$'),
          region text NOT NULL DEFAULT 'ke-nairobi',
          retention_days int NOT NULL DEFAULT 7 CHECK (retention_days BETWEEN 1 AND 365),
          status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended')),
          created_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE TABLE users (
          id uuid PRIMARY KEY,
          email citext NOT NULL UNIQUE,
          name text NOT NULL DEFAULT '',
          password_hash text NOT NULL,
          totp_secret text,
          is_platform_admin boolean NOT NULL DEFAULT false,
          is_active boolean NOT NULL DEFAULT true,
          created_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE TABLE memberships (
          user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          role text NOT NULL CHECK (role IN ('tenant_admin', 'operator', 'viewer')),
          created_at timestamptz NOT NULL DEFAULT now(),
          PRIMARY KEY (user_id, tenant_id)
        );
        CREATE INDEX memberships_tenant_idx ON memberships (tenant_id, user_id);

        CREATE TABLE refresh_tokens (
          id uuid PRIMARY KEY,
          user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          tenant_id uuid REFERENCES tenants(id) ON DELETE CASCADE,
          family_id uuid NOT NULL,
          token_hash text NOT NULL UNIQUE,
          expires_at timestamptz NOT NULL,
          revoked_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX refresh_tokens_family_idx ON refresh_tokens (family_id);

        CREATE TABLE media_nodes (
          id uuid PRIMARY KEY,
          name text NOT NULL UNIQUE,
          region text NOT NULL,
          webrtc_base_url text NOT NULL,
          hls_base_url text NOT NULL,
          internal_api_url text NOT NULL,
          is_active boolean NOT NULL DEFAULT true
        );

        CREATE TABLE sites (
          id uuid PRIMARY KEY,
          tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          name text NOT NULL CHECK (length(name) BETWEEN 1 AND 200),
          address text NOT NULL DEFAULT '',
          timezone text NOT NULL DEFAULT 'Africa/Nairobi',
          created_at timestamptz NOT NULL DEFAULT now(),
          UNIQUE (tenant_id, id)
        );
        CREATE INDEX sites_tenant_idx ON sites (tenant_id, name);

        CREATE TABLE cameras (
          id uuid PRIMARY KEY,
          tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          site_id uuid,
          gateway_id uuid,
          media_node_id uuid NOT NULL REFERENCES media_nodes(id),
          name text NOT NULL CHECK (length(name) BETWEEN 1 AND 200),
          source_type text NOT NULL CHECK (source_type IN ('sim', 'rtsp', 'gateway')),
          main_url_enc bytea,
          sub_url_enc bytea,
          onvif_profile text CHECK (onvif_profile IN ('S', 'T')),
          ptz_capable boolean NOT NULL DEFAULT false,
          enabled boolean NOT NULL DEFAULT true,
          status text NOT NULL DEFAULT 'unknown' CHECK (status IN ('unknown', 'online', 'offline')),
          last_seen timestamptz,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          UNIQUE (tenant_id, id),
          -- A camera can only sit in a site of the same tenant.
          FOREIGN KEY (tenant_id, site_id) REFERENCES sites (tenant_id, id) ON DELETE SET NULL (site_id)
        );
        CREATE INDEX cameras_tenant_idx ON cameras (tenant_id, site_id, name);

        CREATE TABLE camera_permissions (
          tenant_id uuid NOT NULL,
          camera_id uuid NOT NULL,
          user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          can_view boolean NOT NULL DEFAULT true,
          can_playback boolean NOT NULL DEFAULT false,
          can_export boolean NOT NULL DEFAULT false,
          can_ptz boolean NOT NULL DEFAULT false,
          PRIMARY KEY (camera_id, user_id),
          FOREIGN KEY (tenant_id, camera_id) REFERENCES cameras (tenant_id, id) ON DELETE CASCADE,
          FOREIGN KEY (user_id, tenant_id) REFERENCES memberships (user_id, tenant_id) ON DELETE CASCADE
        );
        CREATE INDEX camera_permissions_tenant_idx ON camera_permissions (tenant_id, user_id);
        """
    )

    # Audit log: partitioned by month, indexes lead with tenant_id, append-only.
    _run(
        """
        CREATE TABLE audit_log (
          id uuid NOT NULL,
          at timestamptz NOT NULL DEFAULT now(),
          tenant_id uuid,
          user_id uuid,
          action text NOT NULL,
          target_type text,
          target_id text,
          ip inet,
          user_agent text,
          request_id text,
          detail jsonb NOT NULL DEFAULT '{}'::jsonb,
          PRIMARY KEY (id, at)
        ) PARTITION BY RANGE (at);
        CREATE INDEX audit_log_tenant_at_idx ON audit_log (tenant_id, at DESC);
        CREATE INDEX audit_log_tenant_action_idx ON audit_log (tenant_id, action, at DESC);
        CREATE TABLE audit_log_default PARTITION OF audit_log DEFAULT;

        CREATE FUNCTION audit_log_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'audit_log is append-only';
        END $$;
        CREATE TRIGGER audit_log_no_update BEFORE UPDATE OR DELETE ON audit_log
          FOR EACH ROW EXECUTE FUNCTION audit_log_immutable();
        """
    )
    months = _month_starts(date(2026, 11, 1), 18)
    for start, end in pairwise(months):
        op.execute(
            f"CREATE TABLE audit_log_{start:%Y_%m} PARTITION OF audit_log "
            f"FOR VALUES FROM ('{start.isoformat()}') TO ('{end.isoformat()}')"
        )

    # Row-level security: enabled and forced on every table.
    for table in [
        "tenants",
        "users",
        "memberships",
        "refresh_tokens",
        "media_nodes",
        *TENANT_OWNED,
        "audit_log",
    ]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    for table in TENANT_OWNED:
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} USING (tenant_id = {TENANT}) WITH CHECK (tenant_id = {TENANT})"
        )

    _run(
        f"""
        CREATE POLICY tenant_self ON tenants
          USING (
            id = {TENANT}
            OR {PLATFORM}
            OR EXISTS (SELECT 1 FROM memberships m WHERE m.tenant_id = tenants.id AND m.user_id = {USER})
          )
          WITH CHECK ({PLATFORM});

        CREATE POLICY membership_visible ON memberships
          USING (tenant_id = {TENANT} OR user_id = {USER})
          WITH CHECK (tenant_id = {TENANT});

        -- Defined after memberships so the subquery resolves; the subquery is itself subject to RLS.
        CREATE POLICY user_visible ON users FOR SELECT
          USING (
            id = {USER}
            OR email = {LOGIN_EMAIL}::citext
            OR EXISTS (SELECT 1 FROM memberships m WHERE m.user_id = users.id AND m.tenant_id = {TENANT})
          );
        -- New accounts are created by a tenant admin (invite) or the platform seed; RBAC gates who.
        CREATE POLICY user_create ON users FOR INSERT
          WITH CHECK ({TENANT} IS NOT NULL OR {PLATFORM});
        -- A user row is only ever changed by that user (password rehash, profile). A tenant admin can
        -- never edit a person who may also belong to another tenant.
        CREATE POLICY user_update_self ON users FOR UPDATE
          USING (id = {USER}) WITH CHECK (id = {USER});

        CREATE POLICY refresh_owner ON refresh_tokens
          USING (user_id = {USER} OR token_hash = {REFRESH_HASH})
          WITH CHECK (user_id = {USER});

        CREATE POLICY media_nodes_read ON media_nodes FOR SELECT USING (is_active);
        -- Allows the platform seed (platform_admin context) to register nodes; no UPDATE/DELETE grant.
        CREATE POLICY media_nodes_platform ON media_nodes FOR INSERT WITH CHECK ({PLATFORM});

        CREATE POLICY audit_read ON audit_log FOR SELECT USING (tenant_id = {TENANT});
        CREATE POLICY audit_write ON audit_log FOR INSERT
          WITH CHECK (tenant_id = {TENANT} OR tenant_id IS NULL);
        """
    )

    # Grants for the app role. No UPDATE/DELETE on audit_log or media_nodes; no TRUNCATE anywhere.
    _run(
        """
        GRANT SELECT, INSERT, UPDATE ON tenants TO enclave_app;
        GRANT SELECT, INSERT, UPDATE ON users TO enclave_app;
        GRANT SELECT, INSERT, UPDATE, DELETE ON memberships TO enclave_app;
        GRANT SELECT, INSERT, UPDATE, DELETE ON refresh_tokens TO enclave_app;
        GRANT SELECT, INSERT ON media_nodes TO enclave_app;
        GRANT SELECT, INSERT, UPDATE, DELETE ON sites, cameras, camera_permissions TO enclave_app;
        GRANT SELECT, INSERT ON audit_log TO enclave_app;
        """
    )


def downgrade() -> None:
    _run(
        """
        DROP TABLE IF EXISTS audit_log CASCADE;
        DROP FUNCTION IF EXISTS audit_log_immutable();
        DROP TABLE IF EXISTS camera_permissions, cameras, sites, media_nodes, refresh_tokens,
          memberships, users, tenants CASCADE;
        """
    )
