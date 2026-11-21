#!/usr/bin/env bash
# Monthly restore check (SPEC §11): the newest off-site backup is downloaded, decrypted and
# restored into a throwaway database, then sanity-checked and dropped. Production data is not
# touched. Run by journal-restore-check.timer; the result shows in «Настройки».
#
# Uses /etc/journal/backup.env plus:
#   AGE_IDENTITY_FILE=/etc/journal/backup-identity.txt   # the private key (root, chmod 600)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=/dev/null
source "${BACKUP_ENV:-/etc/journal/backup.env}"
: "${AGE_IDENTITY_FILE:?}" "${RCLONE_REMOTE:?}"
COMPOSE=(docker compose -f "$ROOT/infra/docker-compose.prod.yml" --env-file "$ROOT/.env.prod")
CHECK_DB=journal_restore_check
WORK="$(mktemp -d)"

db() { "${COMPOSE[@]}" exec -T db "$@"; }
sql() { db psql --username postgres --dbname "$1" --tuples-only --no-align -v ON_ERROR_STOP=1 -c "$2"; }
report() {
  "${COMPOSE[@]}" exec -T api python manage.py backup_status --restore-check "$1" >/dev/null || true
}
cleanup() {
  db dropdb --username postgres --if-exists "$CHECK_DB" >/dev/null 2>&1 || true
  rm -rf "$WORK"
}
fail() { echo "restore check FAILED: $1" >&2; report failed; exit 1; }
trap cleanup EXIT
trap 'fail "command failed on line $LINENO"' ERR

latest="$(rclone lsf --files-only "$RCLONE_REMOTE" | grep -E '^journal-[0-9TZ]+\.dump\.age$' | sort | tail -n 1)"
[ -n "$latest" ] || fail "no backups in $RCLONE_REMOTE"

# The newest backup must be recent: proves the nightly job runs, not only that old files work.
stamp="${latest#journal-}"
stamp="${stamp%%.*}"
age_hours=$(( ( $(date -u +%s) - $(date -u -d "${stamp:0:4}-${stamp:4:2}-${stamp:6:2}T${stamp:9:2}:${stamp:11:2}:${stamp:13:2}Z" +%s) ) / 3600 ))
[ "$age_hours" -le 48 ] || fail "newest backup $latest is ${age_hours} h old"

rclone copyto "$RCLONE_REMOTE/$latest" "$WORK/$latest"
age --decrypt --identity "$AGE_IDENTITY_FILE" --output "$WORK/backup.dump" "$WORK/$latest"

db dropdb --username postgres --if-exists "$CHECK_DB"
db createdb --username postgres "$CHECK_DB"
db pg_restore --username postgres --dbname "$CHECK_DB" --no-owner --no-privileges \
  --exit-on-error < "$WORK/backup.dump"

# Sanity: the schema is complete and the data is there.
live_migrations="$(sql "$("${COMPOSE[@]}" exec -T db printenv DB_NAME | tr -d '\r')" \
  "SELECT count(*) FROM django_migrations")"
restored_migrations="$(sql "$CHECK_DB" "SELECT count(*) FROM django_migrations")"
[ "$restored_migrations" -gt 0 ] || fail "no migrations in the backup"
[ "$restored_migrations" -le "$live_migrations" ] || fail "backup is newer than the database?"
[ "$(sql "$CHECK_DB" "SELECT count(*) FROM accounts_user")" -gt 0 ] || fail "no users"
[ "$(sql "$CHECK_DB" "SELECT count(*) FROM audit_auditlog")" -gt 0 ] || fail "empty audit log"
[ "$(sql "$CHECK_DB" "SELECT count(*) FROM pg_trigger WHERE tgname = 'audit_auditlog_append_only'")" = 1 ] \
  || fail "the audit trigger is missing"

report ok
echo "restore check ok: $latest (${age_hours} h old, ${restored_migrations} migrations)"
