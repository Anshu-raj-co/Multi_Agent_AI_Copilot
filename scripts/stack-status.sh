#!/usr/bin/env bash
# Show container state and the latest telemetry as seen through the public rFMS API.
# Exit status: 0 only if every sandbox service is running; 1 otherwise.
source "$(dirname "$0")/_compose.sh"
mcop_compose ps --format 'table {{.Name}}\t{{.State}}\t{{.Status}}'
echo
curl -s -w '\nHTTP %{http_code}\n' 'http://127.0.0.1:8081/rfms/vehiclestatuses?latestOnly=true' | head -c 600 || true
echo

running="$(mcop_compose ps --status running --services)"
missing=()
for s in "${MCOP_SERVICES[@]}"; do
  grep -qx "$s" <<<"$running" || missing+=("$s")
done
if [ "${#missing[@]}" -gt 0 ]; then
  echo "NOT RUNNING: ${missing[*]}" >&2
  exit 1
fi
echo "all ${#MCOP_SERVICES[@]} services running"
