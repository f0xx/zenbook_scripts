# shellcheck shell=bash
# After hid-asus sideload/rebind: sync fn-lock, brightness, restart hotkeys.
# Undock-dock fixes Fn+F4 because hotkeys rediscover on USB replug; rebind alone
# often leaves stale event nodes until the listener restarts on the new nodes.

zenbook_post_sideload_refresh() {
	local settle="${1:-2}"

	sleep "${settle}"

	for _share in /usr/share/zenbook-scripts /usr/local/share/zenbook-scripts; do
		if [[ -f "${_share}/lib/protocol.sh" && -f "${_share}/lib/fn_lock.sh" ]]; then
			# shellcheck disable=SC1091
			source "${_share}/lib/protocol.sh"
			# shellcheck disable=SC1091
			source "${_share}/lib/detect.sh"
			# shellcheck disable=SC1091
			source "${_share}/lib/snapshot.sh"
			# shellcheck disable=SC1091
			source "${_share}/lib/fn_lock.sh"
			zenbook_kb_load_config
			break
		fi
	done

	if declare -F zenbook_kb_fn_lock_restore >/dev/null 2>&1; then
		zenbook_kb_fn_lock_restore >/dev/null 2>&1 || true
	fi

	for _sleep in /usr/bin/kb-brightness-sleep /usr/local/bin/kb-brightness-sleep; do
		if [[ -x "${_sleep}" ]]; then
			"${_sleep}" restore >/dev/null 2>&1 || true
			break
		fi
	done

	if command -v rc-service >/dev/null 2>&1 && [[ -x /etc/init.d/zenbook-kb-hotkeys ]]; then
		rc-service zenbook-kb-hotkeys restart >/dev/null 2>&1 || true
	elif command -v systemctl >/dev/null 2>&1; then
		systemctl restart zenbook-kb-hotkeys.service >/dev/null 2>&1 || true
	fi
}
