#!/usr/bin/env bash
# Stop the sandbox. Pass --volumes to also delete InfluxDB/Grafana data (clean start).
source "$(dirname "$0")/_compose.sh"
mcop_compose down "$@"
