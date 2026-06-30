#!/usr/bin/env bash
# =============================================================================
# deploy.sh — server-side deploy for the RDL AI Sales stack.
#
#   ./deploy/deploy.sh <IMAGE_TAG>
#
# Pulls the requested GHCR image tag, brings the stack up, health-gates it, and
# automatically rolls back to the last known-good tag if the health check fails.
# Persistent volumes (redis_data, linkedin_session) are never touched.
#
# Run from the repo root on the server. Requires a root `.env` containing the
# compose-interpolation vars (e.g. GRAFANA_ADMIN_PASSWORD) and a git-ignored
# backend/.env.prod (chmod 600) with the runtime application secrets.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
cd "$REPO_DIR"

COMPOSE_FILES=(-f docker-compose.yaml -f docker-compose.prod.yaml -f docker-compose.registry.yaml)
LAST_GOOD_FILE="$SCRIPT_DIR/.last_good_tag"
LOG_FILE="$SCRIPT_DIR/deploy.log"

# Tee all output to a log for post-mortems.
exec > >(tee -a "$LOG_FILE") 2>&1

NEW_TAG="${1:-}"
if [[ -z "$NEW_TAG" ]]; then
  echo "ERROR: usage: deploy.sh <IMAGE_TAG>"
  exit 2
fi

# Previous good tag (for rollback). Falls back to the tag currently running.
PREVIOUS_TAG=""
if [[ -f "$LAST_GOOD_FILE" ]]; then
  PREVIOUS_TAG="$(cat "$LAST_GOOD_FILE")"
fi
if [[ -z "$PREVIOUS_TAG" ]]; then
  # Fall back to the tag of the image the backend is currently running.
  running_ref="$(docker inspect --format '{{ .Config.Image }}' rdl_backend 2>/dev/null || true)"
  PREVIOUS_TAG="${running_ref##*:}"
  # Guard against a digest-pinned or untagged ref.
  [[ "$PREVIOUS_TAG" == "$running_ref" ]] && PREVIOUS_TAG=""
fi

echo "============================================================"
echo "Deploy $(date -u +%FT%TZ)"
echo "  New tag:      $NEW_TAG"
echo "  Previous tag: ${PREVIOUS_TAG:-<none>}"
echo "============================================================"

compose() { docker compose "${COMPOSE_FILES[@]}" "$@"; }

# --- Optional DB backup (set BACKUP_DB=true in the server .env to enable) -----
backup_db() {
  if [[ "${BACKUP_DB:-false}" != "true" ]]; then
    echo "DB backup skipped (BACKUP_DB != true)."
    return 0
  fi
  local stamp out
  stamp="$(date -u +%Y%m%d-%H%M%S)"
  out="$SCRIPT_DIR/backups/db-$stamp.sql.gz"
  mkdir -p "$SCRIPT_DIR/backups"
  echo "Backing up database to $out ..."
  PGPASSWORD="${POSTGRES_PASSWORD:?set in env}" pg_dump \
    -h "${POSTGRES_SERVER:-host.docker.internal}" -p "${POSTGRES_PORT:-6432}" \
    -U "${POSTGRES_USER:?set in env}" "${POSTGRES_DB:?set in env}" \
    | gzip > "$out"
  # Keep only the 7 most recent backups.
  ls -1t "$SCRIPT_DIR"/backups/db-*.sql.gz | tail -n +8 | xargs -r rm -f
}

bring_up() {
  local tag="$1"
  echo ">>> Pulling images at tag: $tag"
  IMAGE_TAG="$tag" compose pull backend frontend
  echo ">>> Starting stack at tag: $tag"
  IMAGE_TAG="$tag" compose up -d --no-build --remove-orphans
}

rollback() {
  if [[ -z "$PREVIOUS_TAG" ]]; then
    echo "!!! No previous tag recorded — cannot auto-rollback. Stack may be down."
    return 1
  fi
  echo "!!! Health check failed — rolling back to $PREVIOUS_TAG"
  bring_up "$PREVIOUS_TAG"
  if "$SCRIPT_DIR/healthcheck.sh"; then
    echo "<<< Rollback to $PREVIOUS_TAG is healthy."
  else
    echo "!!! Rollback target $PREVIOUS_TAG is ALSO unhealthy. Manual intervention required."
  fi
}

# --- Deploy -------------------------------------------------------------------
backup_db
bring_up "$NEW_TAG"

echo ">>> Waiting for health gate ..."
if "$SCRIPT_DIR/healthcheck.sh"; then
  echo "$NEW_TAG" > "$LAST_GOOD_FILE"
  echo ">>> Deploy OK. Pruning dangling images (volumes preserved) ..."
  docker image prune -f >/dev/null
  echo "============================================================"
  echo "SUCCESS — now running tag $NEW_TAG"
  echo "============================================================"
else
  rollback
  exit 1
fi
