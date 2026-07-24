#!/bin/bash
# Sleep / lid hooks for platform-fan-control + platform_profile restore.
#
# Usage:
#   zenbook-fan-control-hook pre|post|lid-close|lid-open
#
# On resume (post / lid-open), restore the last explicit CLI platform_profile
# and pwm mode before adaptive fan-control re-evaluates rules. Adaptive
# sleep_pre powersave does not overwrite that saved state.

set -euo pipefail

CMD="${1:-}"

_restore_saved() {
	for c in /usr/bin/platform-fan /usr/local/bin/platform-fan; do
		if [[ -x "${c}" ]]; then
			"${c}" restore >/dev/null 2>&1 || true
			return 0
		fi
	done
	for c in /usr/bin/kb-platform-profile /usr/local/bin/kb-platform-profile; do
		if [[ -x "${c}" ]]; then
			"${c}" restore >/dev/null 2>&1 || true
			break
		fi
	done
}

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

case "${CMD}" in
pre)
	if [[ -n "${BIN}" && -x "${BIN}" ]]; then
		"${BIN}" event sleep_pre || true
	fi
	;;
post)
	_restore_saved
	if [[ -n "${BIN}" && -x "${BIN}" ]]; then
		"${BIN}" event sleep_post || true
	fi
	;;
lid-close)
	if [[ -n "${BIN}" && -x "${BIN}" ]]; then
		"${BIN}" event lid_close || true
	fi
	;;
lid-open)
	_restore_saved
	if [[ -n "${BIN}" && -x "${BIN}" ]]; then
		"${BIN}" event lid_open || true
	fi
	;;
*)
	echo "Usage: $0 pre|post|lid-close|lid-open" >&2
	exit 2
	;;
esac
