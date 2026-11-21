#!/usr/bin/env bash
# Proves the production split of database roles (SPEC §11, stage 7):
# the owner runs migrations; the app role writes rows but cannot touch the audit log,
# alter or drop tables, or disable the append-only trigger.
#
# Needs a PostgreSQL superuser (only to create the throwaway roles and database):
#   PGHOST=localhost SUPERUSER=postgres SUPERUSER_PASSWORD=… infra/scripts/check-db-roles.sh
set -euo pipefail

: "${PGHOST:=localhost}"
: "${PGPORT:=5432}"
: "${SUPERUSER:=postgres}"
: "${SUPERUSER_PASSWORD:?set SUPERUSER_PASSWORD}"
: "${PSQL:=psql}"
DB=journal_roles_check
OWNER=roles_check_owner
APP=roles_check_app

as_superuser() {
  PGPASSWORD="$SUPERUSER_PASSWORD" "$PSQL" -h "$PGHOST" -p "$PGPORT" -U "$SUPERUSER" \
    -v ON_ERROR_STOP=1 -q -d postgres "$@"
}
as_app() {
  PGPASSWORD=app-check "$PSQL" -h "$PGHOST" -p "$PGPORT" -U "$APP" -d "$DB" \
    -v ON_ERROR_STOP=1 -qtc "$1"
}
cleanup() {
  as_superuser -c "DROP DATABASE IF EXISTS $DB" -c "DROP ROLE IF EXISTS $APP" \
    -c "DROP ROLE IF EXISTS $OWNER" >/dev/null 2>&1 || true
}
trap cleanup EXIT
cleanup

as_superuser \
  -c "CREATE ROLE $OWNER LOGIN PASSWORD 'owner-check' NOSUPERUSER NOCREATEROLE NOCREATEDB" \
  -c "CREATE ROLE $APP LOGIN PASSWORD 'app-check' NOSUPERUSER NOCREATEROLE NOCREATEDB" \
  -c "CREATE DATABASE $DB OWNER $OWNER" \
  -c "REVOKE ALL ON DATABASE $DB FROM PUBLIC"

cd "$(dirname "$0")/../../backend"
export DJANGO_SETTINGS_MODULE=config.settings.test DB_HOST="$PGHOST" DB_PORT="$PGPORT" DB_NAME="$DB"
DB_USER=$OWNER DB_PASSWORD=owner-check uv run python manage.py migrate --noinput -v0
DB_USER=$OWNER DB_PASSWORD=owner-check uv run python manage.py db_grants --app-role $APP
DB_USER=$OWNER DB_PASSWORD=owner-check uv run python manage.py db_grants --app-role $APP --check

# The application itself works under the app role: it reads and writes rows.
DB_USER=$APP DB_PASSWORD=app-check uv run python manage.py shell -c \
  "from apps.core.models import CenterSettings; s = CenterSettings.load(); s.save(); print('app role: ORM read/write ok')"
as_app "INSERT INTO audit_auditlog (at, actor_role, user_agent, action, entity_type, entity_id, reason)
        VALUES (now(), '', '', 'check.insert', 'check', '1', '')"

# …and nothing beyond rows.
failed=0
for statement in \
  "UPDATE audit_auditlog SET reason = 'forged'" \
  "DELETE FROM audit_auditlog" \
  "TRUNCATE audit_auditlog" \
  "ALTER TABLE audit_auditlog DISABLE TRIGGER audit_auditlog_append_only" \
  "DROP TABLE accounts_user" \
  "CREATE TABLE intruder (id int)"; do
  if as_app "$statement" >/dev/null 2>&1; then
    echo "✗ the app role could: $statement"
    failed=1
  fi
done
[ "$failed" = 0 ] || exit 1
echo "✓ app role: rows only; the audit log is append-only even for the application"
