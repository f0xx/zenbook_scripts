#!/usr/bin/env bash
# Pure bash entry point for keyboard brightness (sources lib/ transports).

set -euo pipefail
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/bin/kb-brightness" "$@"
