#!/usr/bin/env bash
# Boot-time sideload of UX8406 patched hid-asus.ko (OpenRC / elogind systems).
# Install: /usr/local/libexec/zenbook-hid-asus-boot.sh

set -euo pipefail

CONF="/etc/conf.d/zenbook-kb-hid-asus"
SWITCH="${ZENBOOK_HID_SWITCH:-/usr/local/libexec/zenbook-hid-asus-switch}"

if [[ -f "${CONF}" ]]; then
	# shellcheck disable=SC1090
	source "${CONF}"
fi

case "${sideload:-yes}" in
	no|false|0|off) exit 0 ;;
	auto)
		;;
	yes|true|1|on|"") ;;
	*)
		echo "Unknown sideload=${sideload} in ${CONF}" >&2
		exit 1
		;;
esac

KVER="$(uname -r)"
KO="${ko_path:-/usr/lib/modules/zenbook-hid-asus/${KVER}/hid-asus.ko}"
export ZENBOOK_HID_KO="${KO}"
export ZENBOOK_FN_LOCK_DEFAULT="${fn_lock_default:-0}"
export ZENBOOK_FN_LOCK_ALLOW_TOGGLE="${fn_lock_allow_toggle:-0}"
export ZENBOOK_FN_ROW_POLICY="${fn_row_policy:-0}"
export ZENBOOK_HID_QUICK_RELOAD="${ZENBOOK_HID_QUICK_RELOAD:-0}"
export ZENBOOK_RC_SETTLE_SECS="${ZENBOOK_RC_SETTLE_SECS:-0}"

# Fn-lock is applied by the kernel on insmod (fn_lock_default).  Quick reload
# skips rmmod and cannot change the driver's fn_lock state.
if [[ -f /usr/local/share/zenbook-scripts/lib/protocol.sh \
	&& -f /usr/local/share/zenbook-scripts/lib/fn_lock.sh ]]; then
	# shellcheck disable=SC1091
	source /usr/local/share/zenbook-scripts/lib/protocol.sh
	# shellcheck disable=SC1091
	source /usr/local/share/zenbook-scripts/lib/detect.sh
	# shellcheck disable=SC1091
	source /usr/local/share/zenbook-scripts/lib/snapshot.sh
	# shellcheck disable=SC1091
	source /usr/local/share/zenbook-scripts/lib/fn_lock.sh
	zenbook_kb_load_config
	if declare -F zenbook_kb_fn_lock_needs_full_reload >/dev/null 2>&1 \
		&& zenbook_kb_fn_lock_needs_full_reload; then
		export ZENBOOK_HID_QUICK_RELOAD=0
	fi
fi

if [[ ! -f "${KO}" ]]; then
	logger -t zenbook-hid-asus "boot: missing ${KO} — build/install oot module first"
	exit 0
fi

wait_max="${usb_wait_secs:-15}"
waited=0
while ! lsusb -d 0b05:1b2c >/dev/null 2>&1; do
	if [[ "${sideload:-yes}" == auto ]]; then
		logger -t zenbook-hid-asus "boot: keyboard not docked (auto), skip"
		exit 0
	fi
	if (( waited >= wait_max )); then
		logger -t zenbook-hid-asus "boot: keyboard not docked after ${wait_max}s, skip"
		exit 0
	fi
	sleep 1
	waited=$((waited + 1))
done

if [[ ! -x "${SWITCH}" ]]; then
	logger -t zenbook-hid-asus "boot: switch script missing: ${SWITCH}"
	exit 1
fi

if "${SWITCH}" sideload --no-watchdog; then
	logger -t zenbook-hid-asus "boot: sideload OK (${KO})"
else
	logger -t zenbook-hid-asus "boot: sideload failed — stock hid_asus remains"
	exit 1
fi

if [[ -x /usr/local/bin/kb-brightness-sleep ]]; then
	if /usr/local/bin/kb-brightness-sleep restore; then
		logger -t zenbook-hid-asus "boot: restored keyboard backlight from snapshot"
	else
		logger -t zenbook-hid-asus "boot: brightness restore skipped (no snapshot)"
	fi
fi

if declare -F zenbook_kb_fn_lock_restore >/dev/null 2>&1; then
	if fn_lock="$(zenbook_kb_fn_lock_restore)"; then
		logger -t zenbook-hid-asus "boot: restored fn-lock mode $(zenbook_kb_fn_lock_mode_name "${fn_lock}" 2>/dev/null || echo "${fn_lock}")"
	else
		logger -t zenbook-hid-asus "boot: fn-lock restore failed"
	fi
fi
rm -f /run/zenbook-hid-asus/reload-kind
