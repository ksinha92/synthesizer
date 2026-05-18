#!/usr/bin/env bash
#
# DataWrangler demo data loader.
#
# Usage:
#   ./scripts/demo-load.sh                # Load default (50) demo projects
#   ./scripts/demo-load.sh 100            # Load 100 demo projects
#   ./scripts/demo-load.sh clean          # Remove all demo-seeded data
#   ./scripts/demo-load.sh status         # Show how many demo projects exist
#   ./scripts/demo-load.sh reload         # Clean then reload (default 50)
#   ./scripts/demo-load.sh reload 75      # Clean then reload N projects
#
# Only rows tagged with the `demo_seed=dashboard-v1` marker are touched.
# Real project data is never modified.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/docker-compose.dev.yml"
SERVICE="backend"

cyan()   { printf "\033[36m%s\033[0m\n" "$1"; }
green()  { printf "\033[32m%s\033[0m\n" "$1"; }
yellow() { printf "\033[33m%s\033[0m\n" "$1"; }
red()    { printf "\033[31m%s\033[0m\n" "$1" 1>&2; }

require_backend() {
  if ! docker compose -f "${COMPOSE_FILE}" ps --status running --services 2>/dev/null | grep -q "^${SERVICE}$"; then
    red "Backend container is not running."
    red "Start it with:  docker compose -f docker-compose.dev.yml up -d backend postgres"
    exit 1
  fi
}

run_seed() { docker compose -f "${COMPOSE_FILE}" exec -T "${SERVICE}" python -m scripts.seed_dashboard_demo "$@"; }

cmd="${1:-seed}"
arg="${2:-}"

case "${cmd}" in
  seed|"" )
    require_backend
    n="${arg:-50}"
    cyan "Seeding ${n} demo project(s)…"
    run_seed --seed "${n}"
    green "Done. Dashboard is ready for demo."
    ;;
  clean|cleanup )
    require_backend
    yellow "Removing demo-seeded data only (real data is untouched)…"
    run_seed --cleanup
    green "Done."
    ;;
  status|count )
    require_backend
    run_seed --count
    ;;
  reload )
    require_backend
    n="${arg:-50}"
    yellow "Cleaning…"
    run_seed --cleanup
    cyan "Reseeding ${n} demo project(s)…"
    run_seed --seed "${n}"
    green "Done."
    ;;
  [0-9]* )
    # First arg is a number → treat as seed count
    require_backend
    cyan "Seeding ${cmd} demo project(s)…"
    run_seed --seed "${cmd}"
    green "Done. Dashboard is ready for demo."
    ;;
  -h|--help|help )
    sed -n '2,18p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    ;;
  * )
    red "Unknown command: ${cmd}"
    red "Run: $0 --help"
    exit 2
    ;;
esac
