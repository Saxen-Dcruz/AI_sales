#!/usr/bin/env bash
# =============================================================================
# rollback.sh — manually redeploy a specific (previously-built) image tag.
#
#   ./deploy/rollback.sh <IMAGE_TAG>     # roll to a specific tag
#   ./deploy/rollback.sh                 # roll to the last known-good tag
#
# Use when a bad deploy slipped past the health gate, or to pin back to an
# earlier release. Pulls the tag, brings the stack up, and health-checks it.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
cd "$REPO_DIR"

COMPOSE_FILES=(-f docker-compose.yaml -f docker-compose.prod.yaml -f docker-compose.registry.yaml)
LAST_GOOD_FILE="$SCRIPT_DIR/.last_good_tag"

TAG="${1:-}"
if [[ -z "$TAG" ]]; then
  [[ -f "$LAST_GOOD_FILE" ]] || { echo "ERROR: no tag given and no .last_good_tag recorded."; exit 2; }
  TAG="$(cat "$LAST_GOOD_FILE")"
fi

echo ">>> Rolling to tag: $TAG"
IMAGE_TAG="$TAG" docker compose "${COMPOSE_FILES[@]}" pull backend frontend
IMAGE_TAG="$TAG" docker compose "${COMPOSE_FILES[@]}" up -d --no-build --remove-orphans

if "$SCRIPT_DIR/healthcheck.sh"; then
  echo "$TAG" > "$LAST_GOOD_FILE"
  echo "SUCCESS — now running tag $TAG"
else
  echo "WARNING — tag $TAG is unhealthy. Investigate with: docker compose ${COMPOSE_FILES[*]} logs"
  exit 1
fi
