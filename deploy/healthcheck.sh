#!/usr/bin/env bash
# =============================================================================
# healthcheck.sh — verify the running stack is healthy.
#
# Polls the backend /health endpoint and the frontend HTTP listener with
# retries + backoff. Exits 0 when both pass, non-zero otherwise. Used as the
# deploy gate by deploy.sh / rollback.sh, and runnable standalone for spot checks.
#
# Override the defaults via env if your host port mapping differs:
#   BACKEND_URL   (default http://localhost:8003/health)
#   FRONTEND_URL  (default http://localhost:8080/)
#   RETRIES       (default 12)   ATTEMPT_DELAY (default 5s)
# =============================================================================
set -uo pipefail

BACKEND_URL="${BACKEND_URL:-http://localhost:8003/health}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:8080/}"
RETRIES="${RETRIES:-12}"
ATTEMPT_DELAY="${ATTEMPT_DELAY:-5}"

check_backend() {
  # Expect HTTP 200 and a JSON body containing "UP".
  local body
  body="$(curl -fsS --max-time 5 "$BACKEND_URL" 2>/dev/null)" || return 1
  echo "$body" | grep -q '"status"[[:space:]]*:[[:space:]]*"UP"'
}

check_frontend() {
  # nginx answers on 8080 with a 301 redirect to HTTPS — any HTTP code from the
  # server (not a connection failure) means it is up.
  curl -fsS -o /dev/null --max-time 5 "$FRONTEND_URL" 2>/dev/null \
    || curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$FRONTEND_URL" 2>/dev/null | grep -qE '^[23]'
}

for ((i = 1; i <= RETRIES; i++)); do
  be="DOWN"; fe="DOWN"
  check_backend  && be="UP"
  check_frontend && fe="UP"
  echo "[$i/$RETRIES] backend=$be frontend=$fe"
  if [[ "$be" == "UP" && "$fe" == "UP" ]]; then
    echo "Health check passed."
    exit 0
  fi
  sleep "$ATTEMPT_DELAY"
done

echo "Health check FAILED after $RETRIES attempts (backend=$be frontend=$fe)."
exit 1
