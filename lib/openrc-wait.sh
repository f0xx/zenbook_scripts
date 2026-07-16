# shellcheck shell=bash
# Busy-wait helpers for OpenRC service handoff (avoid flock races on restart).

ZENBOOK_RC_WAIT_INTERVAL="${ZENBOOK_RC_WAIT_INTERVAL:-0.2}"

# Wait until the named service is fully stopped (status + pidfile).
zenbook_rc_wait_stopped() {
	local svc="${1:-}" max="${2:-15}" i=0 pidfile
	[[ -n "${svc}" ]] || return 1
	pidfile="/run/${svc}.pid"
	while (( i < max )); do
		if command -v rc-service >/dev/null 2>&1; then
			local st
			st="$(rc-service -q "${svc}" status 2>&1 || true)"
			if [[ "${st}" == *"stopped"* && "${st}" != *"starting"* ]]; then
				if [[ ! -f "${pidfile}" ]]; then
					return 0
				fi
				if ! kill -0 "$(tr -d '[:space:]' < "${pidfile}")" 2>/dev/null; then
					return 0
				fi
			fi
		elif [[ ! -f "${pidfile}" ]]; then
			return 0
		fi
		sleep "${ZENBOOK_RC_WAIT_INTERVAL}"
		i=$((i + 1))
	done
	return 1
}

# Wait until the named service is not in OpenRC "starting" state.
zenbook_rc_wait_not_starting() {
	local svc="${1:-}" max="${2:-20}" i=0
	[[ -n "${svc}" ]] || return 1
	while (( i < max )); do
		if command -v rc-service >/dev/null 2>&1; then
			local st
			st="$(rc-service -q "${svc}" status 2>&1 || true)"
			if [[ "${st}" != *"starting"* ]]; then
				return 0
			fi
		else
			return 0
		fi
		sleep "${ZENBOOK_RC_WAIT_INTERVAL}"
		i=$((i + 1))
	done
	return 1
}
