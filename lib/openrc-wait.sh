# shellcheck shell=bash
# Busy-wait helpers for OpenRC service handoff (avoid flock races on restart).

ZENBOOK_RC_WAIT_INTERVAL="${ZENBOOK_RC_WAIT_INTERVAL:-0.2}"

# Remove /run/<svc>.pid when the named PID is gone (or the file is garbage).
# Safe to call from start_pre of every long-lived zenbook OpenRC unit.
zenbook_rc_clear_stale_pidfile() {
	local pidfile="${1:-}" _pid=""
	[[ -n "${pidfile}" ]] || return 0
	[[ -f "${pidfile}" ]] || return 0
	_pid="$(tr -d '[:space:]' < "${pidfile}" 2>/dev/null || true)"
	if [[ -z "${_pid}" ]]; then
		rm -f "${pidfile}"
		return 0
	fi
	if ! kill -0 "${_pid}" 2>/dev/null; then
		rm -f "${pidfile}"
	fi
	return 0
}

# Convenience: clear stale pid for RC_SVCNAME (default /run/${RC_SVCNAME}.pid).
zenbook_rc_clear_stale_svc_pidfile() {
	local svc="${1:-${RC_SVCNAME:-}}"
	[[ -n "${svc}" ]] || return 0
	zenbook_rc_clear_stale_pidfile "/run/${svc}.pid"
}

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
					rm -f "${pidfile}"
					return 0
				fi
			fi
		elif [[ ! -f "${pidfile}" ]]; then
			return 0
		else
			zenbook_rc_clear_stale_pidfile "${pidfile}"
			[[ ! -f "${pidfile}" ]] && return 0
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
