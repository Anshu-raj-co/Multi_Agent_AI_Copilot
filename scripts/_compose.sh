#!/usr/bin/env bash
# Shared compose invocation for the ResiliencePilot sandbox. Source this file.
set -euo pipefail
MCOP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BLUEPRINT_DIR="$MCOP_ROOT/Fleet Management/fleet-management"
MCOP_PROJECT="multiagent-copilot"
# Telemetry-path services only; fleet-analysis-backend is excluded (build-only, not on the path; see DECISIONS D-003).
MCOP_SERVICES=(influxdb grafana fms-server fms-consumer databroker csv-provider fms-forwarder fms-zenoh-router)
mcop_compose() {
  docker compose -p "$MCOP_PROJECT" \
    --project-directory "$BLUEPRINT_DIR" \
    -f "$BLUEPRINT_DIR/fms-blueprint-compose.yaml" \
    -f "$BLUEPRINT_DIR/fms-blueprint-compose-zenoh.yaml" \
    -f "$MCOP_ROOT/config/compose/multiagent-copilot.override.yaml" \
    "$@"
}
