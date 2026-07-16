# ScreenPad Plus backlight helpers (ASUS Zenbook Duo UX5400 / UX482 / similar).
#
# Mainline asus-wmi exposes /sys/class/backlight/asus_screenpad.
# On kernels before the Denis Benato screenpad power fixes, props.power uses
# inverted semantics vs FB_BLANK_*: non-zero bl_power is required to apply
# brightness / re-enable the panel after it was powered off.

ZENBOOK_SCREENPAD_SYSFS="${ZENBOOK_SCREENPAD_SYSFS:-/sys/class/backlight/asus_screenpad}"
ZENBOOK_SCREENPAD_MAIN_BL="${ZENBOOK_SCREENPAD_MAIN_BL:-}"
ZENBOOK_SCREENPAD_MIN_ON="${ZENBOOK_SCREENPAD_MIN_ON:-20}"
ZENBOOK_SCREENPAD_DEFAULT="${ZENBOOK_SCREENPAD_DEFAULT:-180}"

zenbook_screenpad_config_dir() {
	if [[ -n "${ZENBOOK_KB_CONFIG_DIR:-}" ]]; then
		echo "${ZENBOOK_KB_CONFIG_DIR}"
		return 0
	fi
	# Prefer system state for boot/services (root).
	if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
		echo "/var/lib/zenbook-scripts"
		return 0
	fi
	if [[ -n "${XDG_CONFIG_HOME:-}" ]]; then
		echo "${XDG_CONFIG_HOME}/zenbook-scripts"
		return 0
	fi
	local home="${HOME:-}"
	if [[ -z "${home}" && -n "${SUDO_USER:-}" ]]; then
		home="$(getent passwd "${SUDO_USER}" 2>/dev/null | cut -d: -f6 || true)"
	fi
	echo "${home:-/root}/.config/zenbook-scripts"
}

zenbook_screenpad_state_file() {
	# Shared last-brightness used by user CLI and boot oneshot.
	if [[ -n "${ZENBOOK_SCREENPAD_STATE_FILE:-}" ]]; then
		echo "${ZENBOOK_SCREENPAD_STATE_FILE}"
		return 0
	fi
	echo "/var/lib/zenbook-scripts/screenpad-brightness"
}

zenbook_screenpad_present() {
	[[ -d "${ZENBOOK_SCREENPAD_SYSFS}" ]] \
		&& [[ -f "${ZENBOOK_SCREENPAD_SYSFS}/brightness" ]] \
		&& [[ -f "${ZENBOOK_SCREENPAD_SYSFS}/max_brightness" ]]
}

zenbook_screenpad_max() {
	cat "${ZENBOOK_SCREENPAD_SYSFS}/max_brightness"
}

zenbook_screenpad_read_brightness() {
	cat "${ZENBOOK_SCREENPAD_SYSFS}/brightness"
}

zenbook_screenpad_read_bl_power() {
	cat "${ZENBOOK_SCREENPAD_SYSFS}/bl_power"
}

# Returns 0 if panel is considered powered (quirk: bl_power != 0 OR brightness > 0
# with a live DRM connector). Prefer bl_power quirk state.
zenbook_screenpad_is_on() {
	local power brightness
	power="$(zenbook_screenpad_read_bl_power)"
	brightness="$(zenbook_screenpad_read_brightness)"
	# Quirky mainline path: non-zero bl_power means "apply on + light".
	if [[ "${power}" != "0" ]]; then
		return 0
	fi
	# After upstream-fixed kernels, power=0 is UNBLANK; treat brightness>0 as on.
	if [[ "${brightness}" != "0" ]] && zenbook_screenpad_drm_connected; then
		return 0
	fi
	return 1
}

zenbook_screenpad_drm_connected() {
	local path status modes
	# Prefer the known UX5400EA ScreenPad connector first.
	for path in /sys/class/drm/card0-HDMI-A-2 /sys/class/drm/card0-DP-1 /sys/class/drm/card0-DP-2; do
		[[ -e "${path}/status" ]] || continue
		if [[ "$(cat "${path}/status" 2>/dev/null || true)" == "connected" ]]; then
			echo "${path}"
			return 0
		fi
	done
	# Fallback: connected non-eDP connector with a portrait-ish mode (ScreenPad Plus).
	for path in /sys/class/drm/card*-HDMI-A-* /sys/class/drm/card*-DP-*; do
		[[ -e "${path}/status" ]] || continue
		status="$(cat "${path}/status" 2>/dev/null || true)"
		[[ "${status}" == "connected" ]] || continue
		modes="$(tr '\n' ' ' <"${path}/modes" 2>/dev/null || true)"
		# 1080x2160 / 1920x515-style ScreenPad modes
		if [[ "${modes}" =~ [0-9]+x2[0-9]{3} || "${modes}" =~ [0-9]+x5[0-9]{2} ]]; then
			echo "${path}"
			return 0
		fi
	done
	return 1
}

zenbook_screenpad_write() {
	local file="$1"
	local value="$2"
	if [[ -w "${file}" ]]; then
		printf '%s\n' "${value}" >"${file}"
		return 0
	fi
	if command -v sudo >/dev/null 2>&1; then
		printf '%s\n' "${value}" | sudo tee "${file}" >/dev/null
		return 0
	fi
	echo "Cannot write ${file} (need root or video-group udev rule)" >&2
	return 1
}

zenbook_screenpad_remember() {
	local level="$1"
	local file dir
	file="$(zenbook_screenpad_state_file)"
	dir="$(dirname "${file}")"
	if [[ ! -d "${dir}" ]]; then
		if [[ -w "$(dirname "${dir}")" ]] || [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
			mkdir -p "${dir}"
		elif command -v sudo >/dev/null 2>&1; then
			sudo mkdir -p "${dir}"
			sudo chmod 0775 "${dir}" || true
		else
			# Fall back to user config if /var/lib is not writable.
			file="$(zenbook_screenpad_config_dir)/screenpad-brightness"
			mkdir -p "$(dirname "${file}")"
		fi
	fi
	if [[ -w "${dir}" ]] || [[ -w "${file}" ]]; then
		printf '%s\n' "${level}" >"${file}"
		return 0
	fi
	if command -v sudo >/dev/null 2>&1; then
		printf '%s\n' "${level}" | sudo tee "${file}" >/dev/null
		return 0
	fi
	file="$(zenbook_screenpad_config_dir)/screenpad-brightness"
	mkdir -p "$(dirname "${file}")"
	printf '%s\n' "${level}" >"${file}"
}

zenbook_screenpad_last() {
	local file level
	file="$(zenbook_screenpad_state_file)"
	if [[ -r "${file}" ]]; then
		level="$(tr -d '[:space:]' <"${file}")"
		if [[ "${level}" =~ ^[0-9]+$ ]]; then
			echo "${level}"
			return 0
		fi
	fi
	echo "${ZENBOOK_SCREENPAD_DEFAULT}"
}

zenbook_screenpad_clamp() {
	local level="$1"
	local max min_on
	max="$(zenbook_screenpad_max)"
	min_on="${ZENBOOK_SCREENPAD_MIN_ON}"
	if (( level < 0 )); then
		level=0
	fi
	if (( level > max )); then
		level="${max}"
	fi
	echo "${level}"
}

# Turn panel on with brightness (re-enable quirk: bl_power=1 then brightness).
zenbook_screenpad_on() {
	local level="${1:-}"
	local max
	max="$(zenbook_screenpad_max)"
	if [[ -z "${level}" ]]; then
		level="$(zenbook_screenpad_last)"
	fi
	level="$(zenbook_screenpad_clamp "${level}")"
	if (( level < ZENBOOK_SCREENPAD_MIN_ON )); then
		level="${ZENBOOK_SCREENPAD_MIN_ON}"
	fi
	# Quirk path first (required on 7.1.x before power-semantics fix).
	zenbook_screenpad_write "${ZENBOOK_SCREENPAD_SYSFS}/bl_power" "1" || return 1
	zenbook_screenpad_write "${ZENBOOK_SCREENPAD_SYSFS}/brightness" "${level}" || return 1
	zenbook_screenpad_remember "${level}"
	# Nudge DRM redetect for connectors that appear after EC power-on.
	local conn i
	for (( i = 0; i < 8; i++ )); do
		for conn in /sys/class/drm/card0-HDMI-A-2 /sys/class/drm/card0-DP-1 /sys/class/drm/card0-DP-2 /sys/class/drm/card*-HDMI-A-* /sys/class/drm/card*-DP-*; do
			[[ -e "${conn}/status" ]] || continue
			if [[ -w "${conn}/status" ]]; then
				printf 'detect\n' >"${conn}/status" 2>/dev/null || true
			elif command -v sudo >/dev/null 2>&1; then
				printf 'detect\n' | sudo tee "${conn}/status" >/dev/null 2>&1 || true
			fi
		done
		if zenbook_screenpad_drm_connected >/dev/null 2>&1; then
			break
		fi
		sleep 0.25
	done
	echo "${level}"
}

zenbook_screenpad_off() {
	local current
	current="$(zenbook_screenpad_read_brightness)"
	if (( current > 0 )); then
		zenbook_screenpad_remember "${current}"
	fi
	# Quirk: bl_power=0 issues SCREENPAD_POWER=0 on current mainline.
	zenbook_screenpad_write "${ZENBOOK_SCREENPAD_SYSFS}/bl_power" "0" || return 1
	echo "0"
}

zenbook_screenpad_set() {
	local level="$1"
	if [[ ! "${level}" =~ ^[0-9]+$ ]]; then
		echo "Brightness must be an integer 0-$(zenbook_screenpad_max)" >&2
		return 2
	fi
	level="$(zenbook_screenpad_clamp "${level}")"
	if (( level == 0 )); then
		zenbook_screenpad_off
		return $?
	fi
	zenbook_screenpad_on "${level}"
}

zenbook_screenpad_find_main_backlight() {
	if [[ -n "${ZENBOOK_SCREENPAD_MAIN_BL}" && -d "${ZENBOOK_SCREENPAD_MAIN_BL}" ]]; then
		echo "${ZENBOOK_SCREENPAD_MAIN_BL}"
		return 0
	fi
	local cand
	for cand in /sys/class/backlight/intel_backlight /sys/class/backlight/amdgpu_bl* /sys/class/backlight/*; do
		[[ -d "${cand}" ]] || continue
		[[ "$(basename "${cand}")" == "asus_screenpad" ]] && continue
		[[ -f "${cand}/brightness" && -f "${cand}/max_brightness" ]] || continue
		echo "${cand}"
		return 0
	done
	return 1
}

# Map main panel percentage onto ScreenPad absolute brightness.
zenbook_screenpad_sync_from_main() {
	local main main_cur main_max pct sp_max target min_on
	main="$(zenbook_screenpad_find_main_backlight)" || return 1
	main_cur="$(cat "${main}/brightness")"
	main_max="$(cat "${main}/max_brightness")"
	if (( main_max <= 0 )); then
		return 1
	fi
	pct=$(( main_cur * 100 / main_max ))
	sp_max="$(zenbook_screenpad_max)"
	target=$(( pct * sp_max / 100 ))
	min_on="${ZENBOOK_SCREENPAD_MIN_ON}"
	# Keep ScreenPad powered when main is not fully dark (avoid losing DRM connector).
	if (( main_cur > 0 && target < min_on )); then
		target="${min_on}"
	fi
	if (( main_cur == 0 )); then
		# Dim with main but do not hard-power-off (reconnect is flaky until reboot).
		target="${min_on}"
	fi
	zenbook_screenpad_on "${target}" >/dev/null
	echo "${target}"
}
