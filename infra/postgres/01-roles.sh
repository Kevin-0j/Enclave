#!/bin/sh
# Runs once on first boot of the Postgres volume. Creates the two roles (ADR 0001):
#   enclave_owner  owns the schema, runs migrations (no BYPASSRLS needed; FORCE RLS still applies)
#   enclave_app    the API/workers role: LOGIN, NOBYPASSRLS, not an owner
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v owner_pass="$ENCLAVE_OWNER_PASSWORD" -v app_pass="$ENCLAVE_APP_PASSWORD" <<'SQL'
CREATE ROLE enclave_owner LOGIN PASSWORD :'owner_pass' NOSUPERUSER NOCREATEROLE NOBYPASSRLS;
CREATE ROLE enclave_app   LOGIN PASSWORD :'app_pass'   NOSUPERUSER NOCREATEROLE NOBYPASSRLS;
CREATE DATABASE enclave OWNER enclave_owner;
CREATE DATABASE enclave_test OWNER enclave_owner;
\c enclave
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT ALL ON SCHEMA public TO enclave_owner;
GRANT USAGE ON SCHEMA public TO enclave_app;
\c enclave_test
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT ALL ON SCHEMA public TO enclave_owner;
GRANT USAGE ON SCHEMA public TO enclave_app;
SQL
