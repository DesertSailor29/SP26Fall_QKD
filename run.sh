#!/usr/bin/env bash
# Run one BB84 session with each party in its own Docker container.
#
#   ./run.sh                 Alice and Bob only
#   ./run.sh --eve           Eve intercepts the quantum channel
#   ./run.sh --eve -n 5000   number of pulses Alice sends (default 1000)
set -euo pipefail
cd "$(dirname "$0")"

profiles=()
export QUANTUM_VIA=bob PULSES=1000
while [[ $# -gt 0 ]]; do
  case "$1" in
    --eve) QUANTUM_VIA=eve; profiles=(--profile eve) ;;
    -n|--pulses) PULSES="$2"; shift ;;
    -h|--help) sed -n '2,7p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

trap 'docker compose --profile eve down --remove-orphans >/dev/null 2>&1 || true' EXIT
docker compose "${profiles[@]}" build --quiet
docker compose "${profiles[@]}" up
