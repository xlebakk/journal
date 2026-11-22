#!/usr/bin/env bash
# Nightly backup: pg_dump → age encryption → off-site copy (rclone) → retention
# 14 daily / 8 weekly / 12 monthly. Run by journal-backup.timer as root on the server.
# The result appears in «Настройки» → «Резервные копии».
#
# /etc/journal/backup.env (chmod 600):
#   AGE_RECIPIENTS_FILE=/etc/journal/backup-recipients.txt   # public key(s), age1…
#   RCLONE_REMOTE=offsite:journal-backups                     # any rclone remote:path
#   LOCAL_DIR=/var/backups/journal                            # last 2 days kept locally
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=/dev/null
source "${BACKUP_ENV:-/etc/journal/backup.env}"
: "${AGE_RECIPIENTS_FILE:?}" "${RCLONE_REMOTE:?}" "${LOCAL_DIR:=/var/backups/journal}"
COMPOSE=(docker compose -f "$ROOT/infra/docker-compose.prod.yml" --env-file "$ROOT/.env.prod")

report() {
  "${COMPOSE[@]}" exec -T api python manage.py backup_status --backup "$1" >/dev/null || true
}
trap 'report failed; echo "backup FAILED" >&2' ERR

umask 077
mkdir -p "$LOCAL_DIR"
name="journal-$(date -u +%Y%m%dT%H%M%SZ).dump.age"

# Custom format is compressed and restorable table by table. The dump is encrypted before it
# touches the disk; only the public key is on the server.
# shellcheck disable=SC2016  # the variables expand inside the db container, not here
"${COMPOSE[@]}" exec -T db sh -c \
  'pg_dump --username "$DB_OWNER_USER" --dbname "$DB_NAME" --format=custom --compress=6' \
  | age --encrypt --recipients-file "$AGE_RECIPIENTS_FILE" > "$LOCAL_DIR/$name.part"
mv "$LOCAL_DIR/$name.part" "$LOCAL_DIR/$name"

rclone copyto "$LOCAL_DIR/$name" "$RCLONE_REMOTE/$name"
rclone lsf --files-only "$RCLONE_REMOTE" \
  | python3 "$ROOT/infra/backup/retention.py" \
  | while read -r old; do rclone deletefile "$RCLONE_REMOTE/$old"; done
find "$LOCAL_DIR" -name 'journal-*.dump.age' -mtime +2 -delete

report ok
echo "backup ok: $name"
