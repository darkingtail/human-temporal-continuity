#!/usr/bin/env bash
set -euo pipefail
BACKUP="${HTC_PRIVATE_BACKUP:-$HOME/.htc-private-backups/20260906-public-sanitize/private.bundle}"
TARGET="${1:-.}"
if [ ! -f "$BACKUP" ]; then echo "private bundle not found: $BACKUP" >&2; exit 1; fi
git -C "$TARGET" fetch "$BACKUP" 2>/dev/null || true
echo "Rollback requires restoring the preserved private bundle into a separate clone; public tree is intentionally left sanitized."
