#!/usr/bin/env bash
# Encrypted backup of the assistant's "brain" (SQLite + MEMORY.md).
# Schedule via cron/systemd timer. Requires: sqlite3, gpg.
# Usage: BACKUP_PASSPHRASE=... ./scripts/backup.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB="${DB_PATH:-$ROOT/data/assistant.db}"
MEM="${MEMORY_MD_PATH:-$ROOT/data/MEMORY.md}"
OUT="${BACKUP_DIR:-$ROOT/backups}"
STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"

: "${BACKUP_PASSPHRASE:?set BACKUP_PASSPHRASE for encryption}"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# Consistent online snapshot (does not block the writer thanks to WAL).
sqlite3 "$DB" ".backup '$TMP/assistant.db'"
[ -f "$MEM" ] && cp "$MEM" "$TMP/MEMORY.md" || true

tar -C "$TMP" -czf "$TMP/bundle.tgz" .
gpg --batch --yes --passphrase "$BACKUP_PASSPHRASE" -c \
    -o "$OUT/la-$STAMP.tgz.gpg" "$TMP/bundle.tgz"

# Keep the last 14 backups.
ls -1t "$OUT"/la-*.tgz.gpg | tail -n +15 | xargs -r rm -f
echo "backup -> $OUT/la-$STAMP.tgz.gpg"
