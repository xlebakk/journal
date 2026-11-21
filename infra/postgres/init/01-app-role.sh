#!/bin/sh
# Creates the application role and database. The app never connects as a superuser,
# so it cannot disable the audit-log trigger (SPEC §11).
set -eu

psql -v ON_ERROR_STOP=1 --username postgres --dbname postgres \
  -v app_user="$DB_USER" -v app_password="$DB_PASSWORD" -v app_db="$DB_NAME" <<'SQL'
CREATE ROLE :"app_user" LOGIN PASSWORD :'app_password'
  NOSUPERUSER NOCREATEROLE CREATEDB NOREPLICATION NOBYPASSRLS;
CREATE DATABASE :"app_db" OWNER :"app_user";
SQL
