#!/bin/sh
# Wrapper for ebuilds / scripts: run kernel preflight against a checkout.
# Usage: preflight-hid-asus.sh [--force] [--kdir PATH] [--json]
# Exit codes: same as zenbook_kb.kernel_preflight (0/1/2/3).
set -eu
ROOT=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
FORCE_ARGS=
if [ "${ZENBOOK_KERNEL_FORCE:-}" = "1" ] || [ "${ZENBOOK_KERNEL_FORCE:-}" = "yes" ]; then
	FORCE_ARGS=--force
fi
exec python3 -m zenbook_kb.kernel_preflight --repo-root "${ROOT}" ${FORCE_ARGS} "$@"
