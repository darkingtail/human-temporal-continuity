#!/usr/bin/env bash
set -euo pipefail
BACKUP="${HTC_PRIVATE_BACKUP:-$HOME/.htc-private-backups/20260906-public-sanitize/private.bundle}"
TARGET="${1:-}"
if [ ! -f "$BACKUP" ]; then echo "private bundle not found: $BACKUP" >&2; exit 1; fi
if [ -z "$TARGET" ]; then echo "usage: ROLLBACK.sh <separate-empty-target>" >&2; exit 2; fi
if [ -e "$TARGET" ] && [ -n "$(ls -A "$TARGET" 2>/dev/null)" ]; then
  echo "rollback target must be absent or empty: $TARGET" >&2
  exit 3
fi
git clone --quiet "$BACKUP" "$TARGET"
git -C "$TARGET" rev-parse --verify HEAD >/dev/null
echo "Rollback clone restored from preserved bundle; source working tree unchanged."
