#!/bin/bash
# Safe toggle between stock in-kernel hid_asus and sideloaded OOT hid-asus.ko
#
# Usage:
#   sudo ./switch-hid-asus.sh status
#   sudo ./switch-hid-asus.sh sideload [--watchdog SECS]
#   sudo ./switch-hid-asus.sh keep          # cancel watchdog after manual typing test
#   sudo ./switch-hid-asus.sh stock
#   sudo ./switch-hid-asus.sh verify
#
# sideload starts a background watchdog (default 120s). If you do not run `keep`
# in time, stock is restored automatically — use touchpad + on-screen keyboard,
# SSH, or the laptop's built-in keyboard if the dock stops accepting input.
#
# Does NOT start zenbook-kb-hotkeys (pyusb on if4 bricks the dock).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_KERNEL="$(cd "${SCRIPT_DIR}/.." && pwd)"
INSTALLED_KO="/usr/lib/modules/zenbook-hid-asus/$(uname -r)/hid-asus.ko"
REPO_KO="${REPO_KERNEL}/build/linux-$(uname -r)/hid-asus.ko"
if [[ -n "${ZENBOOK_HID_KO:-}" && -f "${ZENBOOK_HID_KO}" ]]; then
	KO="${ZENBOOK_HID_KO}"
elif [[ -f "${REPO_KO}" ]]; then
	KO="${REPO_KO}"
elif [[ -f "${INSTALLED_KO}" ]]; then
	KO="${INSTALLED_KO}"
else
	KO="${REPO_KO}"
fi
REBIND_SCRIPT="${SCRIPT_DIR}/rebind-hid-asus.sh"
if [[ ! -x "${REBIND_SCRIPT}" && -x /usr/local/libexec/zenbook-hid-asus-rebind ]]; then
	REBIND_SCRIPT="/usr/local/libexec/zenbook-hid-asus-rebind"
fi
_zenbook_source_fn_lock() {
	local root here
	here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
	for root in \
		"$(cd "${here}/../.." 2>/dev/null && pwd)" \
		"/usr/local/share/zenbook-scripts"; do
		if [[ -f "${root}/lib/protocol.sh" && -f "${root}/lib/fn_lock.sh" ]]; then
			set +u
			# shellcheck source=lib/protocol.sh
			source "${root}/lib/protocol.sh"
			# shellcheck source=lib/detect.sh
			source "${root}/lib/detect.sh"
			# shellcheck source=lib/snapshot.sh
			source "${root}/lib/snapshot.sh"
			# shellcheck source=lib/fn_lock.sh
			source "${root}/lib/fn_lock.sh"
			set -u
			return 0
		fi
	done
	return 1
}

_read_snapshot_fn_lock_default() {
	local snap val
	if _zenbook_source_fn_lock; then
		zenbook_kb_load_config
		val="$(zenbook_kb_fn_lock_insmod_default "${ZENBOOK_KB_DEFAULT_SNAPSHOT}" 2>/dev/null || true)"
		if [[ "${val}" =~ ^[01]$ ]]; then
			echo "${val}"
			return 0
		fi
	fi
	echo "${FN_LOCK_DEFAULT}"
}
FN_LOCK_DEFAULT="${ZENBOOK_FN_LOCK_DEFAULT:-0}"
FN_LOCK_ALLOW_TOGGLE="${ZENBOOK_FN_LOCK_ALLOW_TOGGLE:-0}"
FN_ROW_POLICY="${ZENBOOK_FN_ROW_POLICY:-0}"
if [[ -f /etc/conf.d/zenbook-kb-hid-asus ]]; then
	# shellcheck disable=SC1091
	source /etc/conf.d/zenbook-kb-hid-asus
	FN_LOCK_DEFAULT="${fn_lock_default:-${FN_LOCK_DEFAULT}}"
	FN_LOCK_ALLOW_TOGGLE="${fn_lock_allow_toggle:-${FN_LOCK_ALLOW_TOGGLE}}"
	FN_ROW_POLICY="${fn_row_policy:-${FN_ROW_POLICY}}"
fi
SNAPSHOT="/var/tmp/zenbook-hid-asus.snapshot"
RUN_STATE="/run/zenbook-hid-asus"
RELOAD_KIND_FILE="${RUN_STATE}/reload-kind"
KEEP_FILE="${RUN_STATE}/keep"
WATCHDOG_PID="${RUN_STATE}/watchdog.pid"
WATCHDOG_LOG="${RUN_STATE}/watchdog.log"
DEFAULT_WATCHDOG_SECS="${ZENBOOK_HID_WATCHDOG_SECS:-120}"

_zenbook_source_openrc_wait() {
	local root here
	here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
	for root in \
		"$(cd "${here}/../.." 2>/dev/null && pwd)/lib" \
		"/usr/local/share/zenbook-scripts/lib"; do
		if [[ -f "${root}/openrc-wait.sh" ]]; then
			set +u
			# shellcheck source=lib/openrc-wait.sh
			source "${root}/openrc-wait.sh"
			set -u
			return 0
		fi
	done
	return 1
}

_stop_hotkeys() {
	if ! command -v rc-service >/dev/null 2>&1; then
		return 0
	fi
	rc-service -q zenbook-kb-hotkeys stop 2>/dev/null || true
	if _zenbook_source_openrc_wait; then
		zenbook_rc_wait_stopped zenbook-kb-hotkeys 15 || true
	fi
}

_set_reload_kind() {
	mkdir -p "${RUN_STATE}"
	printf '%s\n' "$1" >"${RELOAD_KIND_FILE}"
}

_snapshot() {
	{
		echo "# $(date -Iseconds)"
		echo "module=$(modinfo -n hid_asus 2>/dev/null || echo none)"
		for n in /sys/bus/hid/devices/*0B05*1B2C*; do
			[[ -e "$n" ]] || continue
			drv=$(basename "$(readlink -f "$n/driver" 2>/dev/null)" 2>/dev/null || echo none)
			echo "$(basename "$n") $drv"
		done
	} >"$SNAPSHOT"
	echo "snapshot → $SNAPSHOT"
}

_module_kind() {
	if [[ ! -d /sys/module/hid_asus ]]; then
		echo "none"
		return
	fi
	# insmod of the OOT .ko still makes modinfo -n point at the in-tree path on Gentoo.
	if [[ -r /sys/module/hid_asus/taint ]] && grep -q 'O' /sys/module/hid_asus/taint; then
		echo "sideload"
		return
	fi
	local path
	path="$(modinfo -n hid_asus 2>/dev/null || true)"
	if [[ -f "$KO" && "$path" == "$(readlink -f "$KO" 2>/dev/null || echo "$KO")" ]]; then
		echo "sideload"
	elif [[ "$path" == *"zenbook"* || "$path" == *"build"* ]]; then
		echo "sideload"
	elif [[ "$path" == *"/kernel/"* ]]; then
		echo "stock"
	else
		echo "loaded:$path"
	fi
}

_verify() {
	local ok=0 fail=0
	check() {
		if eval "$2"; then
			echo "  OK  $1"
			ok=$((ok + 1))
		else
			echo "  FAIL $1"
			fail=$((fail + 1))
		fi
	}

	echo "=== verify ==="
	check "USB keyboard docked" "lsusb -d 0b05:1b2c >/dev/null 2>&1"

	local tp_drv="" if4_drv="" kbd_asus=0
	shopt -s nullglob
	for n in /sys/bus/hid/devices/*0B05*1B2C*; do
		[[ -e "$n" ]] || continue
		local path drv rdesc ifnum
		path="$(readlink -f "$n")"
		drv="$(basename "$(readlink -f "$n/driver" 2>/dev/null)" 2>/dev/null || echo none)"
		rdesc="$(wc -c <"$n/report_descriptor" 2>/dev/null || echo 0)"
		[[ "$path" =~ :1\.([0-9]+)/ ]] && ifnum="${BASH_REMATCH[1]}" || ifnum="?"
		if [[ "$ifnum" == "5" || "$rdesc" -ge 200 ]]; then
			tp_drv="$drv"
		elif [[ "$ifnum" == "4" || ( "$rdesc" -ge 90 && "$rdesc" -le 120 ) ]]; then
			if4_drv="$drv"
		elif [[ "$drv" == "asus" ]]; then
			kbd_asus=$((kbd_asus + 1))
		fi
	done
	shopt -u nullglob

	check "touchpad if5 not on asus" "[[ \"$tp_drv\" != \"asus\" && -n \"$tp_drv\" ]]"
	check "input: Primax keyboard node" "grep -rq 'Primax' /sys/class/input/event*/device/name 2>/dev/null"
	check "touchpad input node" "grep -rq 'Touchpad' /sys/class/input/event*/device/name 2>/dev/null"

	local kind
	kind="$(_module_kind)"
	if [[ "$kind" == "sideload" ]]; then
		check "sideload: if4 on asus" "[[ \"$if4_drv\" == \"asus\" ]]"
		check "sideload: keyboard if on asus" "[[ $kbd_asus -ge 1 ]]"
	elif [[ "$kind" == "stock" ]]; then
		check "stock: if4 has HID node" "[[ -n \"$if4_drv\" ]]"
	fi

	echo "module=$kind touchpad=$tp_drv if4=$if4_drv asus_kbd_nodes=$kbd_asus"
	[[ $fail -eq 0 ]]
}

_recover_usb_if4() {
	if ! lsusb -d 0b05:1b2c >/dev/null 2>&1; then
		return 0
	fi
	for p in /sys/bus/usb/devices/*-*; do
		[[ -f "$p/idVendor" && "$(cat "$p/idVendor")" == "0b05" && "$(cat "$p/idProduct")" == "1b2c" ]] || continue
		local port
		port="$(basename "$p")"
		if [[ -d "/sys/bus/usb/devices/${port}:1.4" ]]; then
			echo "${port}:1.4" >"/sys/bus/usb/drivers/usbhid/unbind" 2>/dev/null || true
			sleep 0.3
			echo "${port}:1.4" >"/sys/bus/usb/drivers/usbhid/bind" 2>/dev/null || true
		fi
	done
}

_watchdog_cancel() {
	if [[ -f "$WATCHDOG_PID" ]]; then
		local pid
		pid="$(cat "$WATCHDOG_PID")"
		if kill -0 "$pid" 2>/dev/null; then
			kill "$pid" 2>/dev/null || true
			wait "$pid" 2>/dev/null || true
		fi
		rm -f "$WATCHDOG_PID"
	fi
}

_watchdog_start() {
	local secs="$1"
	_watchdog_cancel
	mkdir -p "$RUN_STATE"
	rm -f "$KEEP_FILE"
	(
		sleep "$secs"
		if [[ -f "$KEEP_FILE" ]]; then
			echo "$(date -Iseconds) watchdog: sideload kept by user" >>"$WATCHDOG_LOG"
			exit 0
		fi
		{
			echo "$(date -Iseconds) watchdog: ${secs}s elapsed — auto-revert to stock"
			echo "  (no 'keep' received; keyboard may be unresponsive)"
		} | tee -a "$WATCHDOG_LOG" >&2
		_cmd_stock_force
	) &
	echo $! >"$WATCHDOG_PID"
}

_watchdog_active() {
	[[ -f "$WATCHDOG_PID" ]] && kill -0 "$(cat "$WATCHDOG_PID")" 2>/dev/null
}

_cmd_stock_force() {
	# Best-effort restore — safe to call from watchdog when keyboard is dead.
	set +e
	_stop_hotkeys
	"${SCRIPT_DIR}/unload-hid-asus.sh" 2>/dev/null
	rmmod hid_asus 2>/dev/null
	modprobe hid_asus 2>/dev/null
	sleep 1
	_recover_usb_if4
	sleep 0.5
	_verify || true
	set -e
}

_cmd_stock() {
	_watchdog_cancel
	rm -f "$KEEP_FILE"
	_stop_hotkeys
	_snapshot
	_cmd_stock_force
	if _verify; then
		echo "stock: OK"
	else
		echo "stock: verify failed — replug keyboard dock" >&2
		return 1
	fi
}

_cmd_keep() {
	if ! _watchdog_active; then
		echo "No active sideload watchdog." >&2
		if [[ "$(_module_kind)" == "sideload" ]]; then
			echo "Sideload appears active without watchdog — run 'stock' to revert if needed."
		fi
		return 1
	fi
	touch "$KEEP_FILE"
	_watchdog_cancel
	echo "keep: sideload confirmed — watchdog cancelled"
	echo "module=$(_module_kind)"
}

_cmd_quick_reload() {
	if [[ "${ZENBOOK_HID_QUICK_RELOAD:-1}" == "0" ]]; then
		return 1
	fi
	if [[ "$(_module_kind)" != "sideload" ]]; then
		return 1
	fi
	if ! lsusb -d 0b05:1b2c >/dev/null 2>&1; then
		return 1
	fi
	if _verify; then
		echo "quick reload: sideload active, bindings OK — skipping rmmod/insmod"
		_set_reload_kind quick
		return 0
	fi
	echo "quick reload: rebinding HID nodes (no module reload)"
	if ! "${REBIND_SCRIPT}"; then
		return 1
	fi
	if ! _verify; then
		return 1
	fi
	echo "quick reload: rebind OK"
	_set_reload_kind quick
	return 0
}

_should_force_full_sideload() {
	_zenbook_source_fn_lock || return 0
	zenbook_kb_load_config
	if declare -F zenbook_kb_fn_lock_needs_full_reload >/dev/null 2>&1 \
		&& zenbook_kb_fn_lock_needs_full_reload; then
		return 0
	fi
	return 1
}

_cmd_sideload() {
	local watchdog_secs="$1"
	local use_watchdog="$2"

	if [[ "${ZENBOOK_HID_QUICK_RELOAD:-0}" == "1" ]] && ! _should_force_full_sideload; then
		if _cmd_quick_reload; then
			if [[ -n "${ZENBOOK_RC_SETTLE_SECS:-}" && "${ZENBOOK_RC_SETTLE_SECS}" -gt 0 ]]; then
				sleep "${ZENBOOK_RC_SETTLE_SECS}"
			fi
			return 0
		fi
	fi

	_set_reload_kind full
	_stop_hotkeys
	if ! lsusb -d 0b05:1b2c >/dev/null 2>&1; then
		echo "Dock the keyboard on USB before sideload." >&2
		return 1
	fi
	if [[ ! -f "$KO" ]]; then
		echo "Missing $KO — run: make -f kernel/Makefile build-current" >&2
		echo "  then: sudo python3 configure.py --defaults --all-yes  (installs to ${INSTALLED_KO})" >&2
		return 1
	fi

	if [[ "$use_watchdog" == "1" ]]; then
		_watchdog_start "$watchdog_secs"
		echo "watchdog: ${watchdog_secs}s — auto-revert to stock unless you run:"
		echo "  sudo $0 keep"
		echo "(use touchpad, on-screen keyboard, SSH, or built-in keyboard if dock input dies)"
		echo
	fi

	_snapshot
	rmmod hid_asus 2>/dev/null || true
	local fn_lock_insmod
	fn_lock_insmod="$(_read_snapshot_fn_lock_default)"
	if ! insmod "$KO" fn_lock_default="${fn_lock_insmod}" \
		fn_lock_allow_toggle="${FN_LOCK_ALLOW_TOGGLE}" \
		fn_row_policy="${FN_ROW_POLICY}"; then
		echo "insmod failed — restoring stock" >&2
		_watchdog_cancel
		_cmd_stock_force
		return 1
	fi
	if ! "${REBIND_SCRIPT}"; then
		echo "rebind failed — restoring stock" >&2
		_watchdog_cancel
		_cmd_stock_force
		return 1
	fi
	if ! _verify; then
		echo "sideload: sysfs verify failed — rolling back to stock" >&2
		_watchdog_cancel
		_cmd_stock_force
		return 1
	fi

	echo "sideload: sysfs checks passed (fn_lock_default=${fn_lock_insmod} fn_row_policy=${FN_ROW_POLICY})"
	if _zenbook_source_fn_lock; then
		zenbook_kb_load_config
		zenbook_kb_fn_lock_clear_toggled 2>/dev/null || true
	fi
	echo "  → type on the docked keyboard now (test a few keys + touchpad)"
	if [[ "$use_watchdog" == "1" ]]; then
		echo "  → if input works:  sudo $0 keep"
		echo "  → otherwise wait ${watchdog_secs}s for automatic stock restore"
	else
		echo "  → watchdog disabled — run 'stock' manually if input fails"
	fi
	echo "Before starting hotkeys: kb-brightness-hotkeys --show-profile  (usb_poll should be False)"
	if [[ -n "${ZENBOOK_RC_SETTLE_SECS:-}" && "${ZENBOOK_RC_SETTLE_SECS}" -gt 0 ]]; then
		sleep "${ZENBOOK_RC_SETTLE_SECS}"
	fi
}

_cmd_status() {
	echo "kernel: $(uname -r)"
	local kind path
	kind="$(_module_kind)"
	path="$(modinfo -n hid_asus 2>/dev/null || echo not loaded)"
	echo "hid_asus: ${kind} (${path})"
	if [[ "$kind" == "sideload" && "$path" == *"/kernel/"* ]]; then
		echo "  (OOT module loaded via insmod — modinfo still shows in-tree path)"
	fi
	lsusb -d 0b05:1b2c 2>/dev/null || echo "USB: keyboard not docked"
	if _watchdog_active; then
		echo "watchdog: ACTIVE (pid $(cat "$WATCHDOG_PID")) — run '$0 keep' to confirm sideload"
	elif [[ -f "$WATCHDOG_LOG" ]]; then
		echo "watchdog log: $WATCHDOG_LOG"
		tail -3 "$WATCHDOG_LOG" 2>/dev/null || true
	fi
	echo
	_verify || true
}

usage() {
	cat <<EOF
Usage: $0 <command> [options]

Commands:
  status              Show module + HID bindings + verify
  sideload [opts]     Load OOT hid-asus.ko and rebind (with watchdog)
  keep                Confirm sideload works — cancel auto-revert
  stock               Restore in-kernel hid_asus
  verify              Run binding checks only

Sideload options:
  --watchdog SECS     Auto-revert after SECS (default: ${DEFAULT_WATCHDOG_SECS})
  --no-watchdog       Skip timed rollback (not recommended)

Environment:
  ZENBOOK_HID_WATCHDOG_SECS   Default watchdog duration

Example:
  sudo $0 sideload --watchdog 90
  # test typing on dock; if OK:
  sudo $0 keep
EOF
	exit 1
}

[[ "$(id -u)" -eq 0 ]] || {
	echo "Run as root (sudo)." >&2
	exit 1
}

CMD="${1:-}"
shift || true

WATCHDOG_SECS="$DEFAULT_WATCHDOG_SECS"
USE_WATCHDOG=1
while [[ $# -gt 0 ]]; do
	case "$1" in
	--watchdog)
		shift
		WATCHDOG_SECS="${1:?--watchdog requires seconds}"
		shift
		;;
	--no-watchdog)
		USE_WATCHDOG=0
		shift
		;;
	*)
		echo "Unknown option: $1" >&2
		usage
		;;
	esac
done

case "$CMD" in
status) _cmd_status ;;
stock) _cmd_stock ;;
keep) _cmd_keep ;;
sideload) _cmd_sideload "$WATCHDOG_SECS" "$USE_WATCHDOG" ;;
verify) _verify ;;
*) usage ;;
esac
