#!/bin/bash
# Sleep / lid hooks for platform-fan-control.
#
# Usage:
#   zenbook-fan-control-hook pre|post|lid-close|lid-open

set -euo pipefail

CMD="${1:-}"
BIN=""
for c in /usr/bin/platform-fan-control /usr/local/bin/platform-fan-control \
	/usr/bin/kb-fan-control /usr/local/bin/kb-fan-control; do
	if [[ -x "${c}" ]]; then
		BIN="${c}"
		break
	fi
done
if [[ -z "${BIN}" ]]; then
	here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
	if [[ -x "${here}/../../bin/platform-fan-control" ]]; then
		BIN="${here}/../../bin/platform-fan-control"
	fi
fi
if [[ -z "${BIN}" || ! -x "${BIN}" ]]; then
	exit 0
fi

case "${CMD}" in
pre)
	"${BIN}" event sleep_pre || true
	;;
post)
	"${BIN}" event sleep_post || true
	;;
lid-close)
	"${BIN}" event lid_close || true
	;;
lid-open)
	"${BIN}" event lid_open || true
	;;
*)
	echo "Usage: $0 pre|post|lid-close|lid-open" >&2
	exit 2
	;;
esac
