#!/bin/bash
# Sleep hooks for platform-session (OpenRC / elogind system-sleep parity).
#
# Install to /usr/local/libexec/zenbook-platform-session-hook (or PATH) and call
# from /lib/systemd/system-sleep/ on elogind systems, or wire manually.
#
# Usage:
#   zenbook-platform-session-hook pre|post [suspend|hibernate]
#
# When using session.json as the orchestrator, disable redundant brightness/fan
# sleep hooks and let platform-session actions call kb-brightness-sleep and
# platform-fan-control instead.

set -euo pipefail

CMD="${1:-}"
MODE="${2:-suspend}"
BIN=""

for c in /usr/bin/platform-session /usr/local/bin/platform-session; do
	if [[ -x "${c}" ]]; then
		BIN="${c}"
		break
	fi
done
if [[ -z "${BIN}" ]]; then
	here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
	if [[ -x "${here}/../../bin/platform-session" ]]; then
		BIN="${here}/../../bin/platform-session"
	fi
fi
if [[ -z "${BIN}" || ! -x "${BIN}" ]]; then
	exit 0
fi

case "${CMD}/${MODE}" in
pre/hibernate|pre/hybrid-sleep|pre/suspend-then-hibernate)
	"${BIN}" run hibernate || true
	;;
pre/*)
	"${BIN}" run sleep || true
	;;
post/hibernate|post/hybrid-sleep|post/suspend-then-hibernate)
	"${BIN}" run hibernate-resume || true
	;;
post/*)
	"${BIN}" run resume || true
	;;
*)
	echo "Usage: $0 pre|post [suspend|hibernate]" >&2
	exit 2
	;;
esac
