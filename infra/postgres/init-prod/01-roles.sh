#!/bin/sh
# Production database roles (stage 7), created once on an empty data volume:
#   DB_OWNER_USER — owns the database and the tables; only the `migrate` job connects as it;
#   DB_USER       — the application: rows only (privileges from `manage.py db_grants`),
#                   so it cannot disable the audit trigger or rewrite the audit log.
# Neither is a superuser; the superuser exists only inside the container.
set -eu

psql -v ON_ERROR_STOP=1 --username postgres --dbname postgres \
  -v owner="$DB_OWNER_USER" -v owner_password="$DB_OWNER_PASSWORD" \
  -v app="$DB_USER" -v app_password="$DB_PASSWORD" -v db="$DB_NAME" <<'SQL'
CREATE ROLE :"owner" LOGIN PASSWORD :'owner_password'
  NOSUPERUSER NOCREATEROLE NOCREATEDB NOREPLICATION NOBYPASSRLS;
CREATE ROLE :"app" LOGIN PASSWORD :'app_password'
  NOSUPERUSER NOCREATEROLE NOCREATEDB NOREPLICATION NOBYPASSRLS;
CREATE DATABASE :"db" OWNER :"owner";
REVOKE ALL ON DATABASE :"db" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"db" TO :"app";
SQL
