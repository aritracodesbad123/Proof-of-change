#!/usr/bin/env bash
# Create (or print) a Nebius Serverless AI Endpoint that serves the operator console.
# Result: a managed https://… URL you can open in a browser (like GCP).
#
# Prerequisites: docker, nebius CLI logged in, jq
# Usage:
#   export IMAGE=docker.io/<you>/poc-console:latest   # already pushed
#   export SUBNET_ID=…                                # from Nebius VPC
#   ./scripts/nebius_console_endpoint.sh
#
# Optional: NAME, PLATFORM, PRESET, NEBIUS_API_KEY (passed into the container)

set -euo pipefail

NAME="${NAME:-poc-console}"
IMAGE="${IMAGE:?set IMAGE to a pushed container image (e.g. docker.io/you/poc-console:latest)}"
SUBNET_ID="${SUBNET_ID:?set SUBNET_ID (Nebius VPC subnet)}"
PLATFORM="${PLATFORM:-cpu-d3}"
PRESET="${PRESET:-4vcpu-16gb}"
PORT="${PORT:-8787}"

if ! command -v nebius >/dev/null; then
  echo "Install and login to the Nebius CLI first: https://docs.nebius.com/cli/" >&2
  exit 1
fi

ENV_ARGS=()
# Token Factory key for Nemotron swarm inside the container
if [[ -n "${NEBIUS_API_KEY:-}" ]]; then
  ENV_ARGS+=(--env "NEBIUS_API_KEY=${NEBIUS_API_KEY}")
fi
if [[ -n "${NEBIUS_PROJECT_ID:-}" ]]; then
  ENV_ARGS+=(--env "NEBIUS_PROJECT_ID=${NEBIUS_PROJECT_ID}")
fi
if [[ -n "${POC_DEMO_REPOS:-}" ]]; then
  ENV_ARGS+=(--env "POC_DEMO_REPOS=${POC_DEMO_REPOS}")
fi

echo "Creating Nebius Endpoint name=${NAME} image=${IMAGE} port=${PORT} auth=none …"
# --auth none → browser can navigate without Authorization header (GCP-like)
nebius ai endpoint create \
  --name "$NAME" \
  --image "$IMAGE" \
  --platform "$PLATFORM" \
  --preset "$PRESET" \
  --container-port "$PORT" \
  --auth none \
  --subnet-id "$SUBNET_ID" \
  "${ENV_ARGS[@]}"

ENDPOINT_ID="$(nebius ai endpoint get-by-name --name "$NAME" --format jsonpath='{.metadata.id}')"
echo "Endpoint id: $ENDPOINT_ID"
echo "Waiting for RUNNING + public https URL …"

for _ in $(seq 1 60); do
  JSON="$(nebius ai endpoint get "$ENDPOINT_ID" --format json)"
  STATE="$(echo "$JSON" | jq -r '.status.state // .status // empty')"
  URL="$(echo "$JSON" | jq -r '[.status.public_endpoints[]? // .status.publicEndpoints[]? // empty] | map(select(startswith("https://"))) | .[0] // empty')"
  if [[ -n "$URL" ]]; then
    echo ""
    echo "Open the operator console:"
    echo "  $URL"
    echo ""
    echo "Health: curl -sS \"$URL/api/health\""
    exit 0
  fi
  echo "  state=${STATE:-?} (no https URL yet)"
  sleep 10
done

echo "Timed out waiting for public URL. Check: nebius ai endpoint get $ENDPOINT_ID" >&2
exit 1
