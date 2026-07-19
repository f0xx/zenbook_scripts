# ASUS asus-nb-wmi fan helpers (UX8406 / UX5400 and similar).
#
# Available:
#   - RPM readout (hwmon fan1_input)
#   - pwm1_enable: 0 = full-on, 2 = firmware auto (1 = manual curve — ENODEV here)
#   - platform_profile / throttle_thermal_policy (quiet / balanced / performance)
#
# Not available on these Zenbooks:
#   - Custom pwm*_auto_point_* fan curves (WMI fan_curve_get_factory_default → ENODEV)

ZENBOOK_ASUS_WMI_PLATFORM="${ZENBOOK_ASUS_WMI_PLATFORM:-/sys/devices/platform/asus-nb-wmi}"
ZENBOOK_THROTTLE_THERMAL_POLICY="${ZENBOOK_THROTTLE_THERMAL_POLICY:-${ZENBOOK_ASUS_WMI_PLATFORM}/throttle_thermal_policy}"

# shellcheck source=lib/platform_profile.sh
: "${ZENBOOK_LIB_PLATFORM_PROFILE:=}"

zenbook_fan_find_hwmon() {
	local d name

	if [[ -n "${ZENBOOK_ASUS_HWMON:-}" && -d "${ZENBOOK_ASUS_HWMON}" ]]; then
		printf '%s\n' "${ZENBOOK_ASUS_HWMON}"
		return 0
	fi

	for d in "${ZENBOOK_ASUS_WMI_PLATFORM}"/hwmon/hwmon*; do
		[[ -d "${d}" ]] || continue
		name="$(tr -d '[:space:]' <"${d}/name" 2>/dev/null || true)"
		if [[ "${name}" == "asus" ]]; then
			printf '%s\n' "${d}"
			return 0
		fi
	done

	for d in /sys/class/hwmon/hwmon*; do
		[[ -d "${d}" ]] || continue
		name="$(tr -d '[:space:]' <"${d}/name" 2>/dev/null || true)"
		if [[ "${name}" == "asus" && -f "${d}/fan1_input" ]]; then
			printf '%s\n' "${d}"
			return 0
		fi
	done

	return 1
}

zenbook_fan_present() {
	zenbook_fan_find_hwmon >/dev/null
}

zenbook_fan_sysfs_write() {
	local path="$1"
	local value="$2"

	if [[ -w "${path}" ]]; then
		printf '%s' "${value}" >"${path}"
		return 0
	fi
	# Never block on a sudo password prompt (daemons / hooks / tray).
	if command -v sudo >/dev/null 2>&1; then
		if printf '%s' "${value}" | sudo -n tee "${path}" >/dev/null 2>&1; then
			return 0
		fi
	fi
	echo "Cannot write ${path} (need root or NOPASSWD sudo -n)" >&2
	return 1
}

zenbook_fan_rpm() {
	local hwmon

	hwmon="$(zenbook_fan_find_hwmon)" || return 1
	printf '%s\n' "$(tr -d '[:space:]' <"${hwmon}/fan1_input")"
}

zenbook_fan_label() {
	local hwmon

	hwmon="$(zenbook_fan_find_hwmon)" || return 1
	if [[ -r "${hwmon}/fan1_label" ]]; then
		tr -d '[:space:]' <"${hwmon}/fan1_label"
	else
		printf 'fan1\n'
	fi
}

# 0=full-on, 2=auto (firmware). 1=manual curve — not supported on UX8406/UX5400.
zenbook_fan_pwm_enable_get() {
	local hwmon

	hwmon="$(zenbook_fan_find_hwmon)" || return 1
	tr -d '[:space:]' <"${hwmon}/pwm1_enable"
}

zenbook_fan_pwm_enable_set() {
	local mode="$1"
	local hwmon

	case "${mode}" in
	0 | full | max | on)
		mode=0
		;;
	2 | auto)
		mode=2
		;;
	1 | manual | curve)
		echo "Manual PWM curves are not exposed on this model (firmware owns the curve)." >&2
		echo "Use: platform-fan auto|full  or  platform-fan quiet|balanced|performance" >&2
		return 1
		;;
	*)
		echo "Unknown pwm mode '${mode}' (use full|auto)" >&2
		return 2
		;;
	esac

	hwmon="$(zenbook_fan_find_hwmon)" || return 1
	zenbook_fan_sysfs_write "${hwmon}/pwm1_enable" "${mode}"
}

zenbook_fan_pwm_mode_name() {
	case "$1" in
	0) printf 'full-on' ;;
	1) printf 'manual-curve' ;;
	2) printf 'auto' ;;
	*) printf 'unknown(%s)' "$1" ;;
	esac
}

zenbook_fan_ttp_get() {
	[[ -r "${ZENBOOK_THROTTLE_THERMAL_POLICY}" ]] || return 1
	tr -d '[:space:]' <"${ZENBOOK_THROTTLE_THERMAL_POLICY}"
}

# Kernel ABI: 0=default/balanced, 1=overboost/performance, 2=silent/quiet
zenbook_fan_ttp_name() {
	case "$1" in
	0) printf 'balanced' ;;
	1) printf 'performance' ;;
	2) printf 'quiet' ;;
	*) printf 'unknown(%s)' "$1" ;;
	esac
}

zenbook_fan_status() {
	local hwmon rpm label pwm_en profile ttp

	hwmon="$(zenbook_fan_find_hwmon)" || {
		echo "asus hwmon with fan1_input not found" >&2
		return 1
	}

	rpm="$(zenbook_fan_rpm)"
	label="$(zenbook_fan_label)"
	pwm_en="$(zenbook_fan_pwm_enable_get)"

	printf 'hwmon:     %s\n' "${hwmon}"
	printf 'fan:       %s\n' "${label}"
	printf 'rpm:       %s\n' "${rpm}"
	printf 'pwm_mode:  %s (%s)\n' "${pwm_en}" "$(zenbook_fan_pwm_mode_name "${pwm_en}")"

	if [[ -r "${ZENBOOK_PLATFORM_PROFILE:-/sys/firmware/acpi/platform_profile}" ]]; then
		profile="$(tr -d '[:space:]' <"${ZENBOOK_PLATFORM_PROFILE:-/sys/firmware/acpi/platform_profile}")"
		printf 'profile:   %s\n' "${profile}"
	fi

	if ttp="$(zenbook_fan_ttp_get 2>/dev/null)"; then
		printf 'throttle:  %s (%s)\n' "${ttp}" "$(zenbook_fan_ttp_name "${ttp}")"
	fi

	if [[ -e "${hwmon}/pwm1_auto_point1_temp" ]]; then
		printf 'curves:    sysfs points present (advanced)\n'
	else
		printf 'curves:    not on this model (normal — firmware auto curve only)\n'
	fi
}

# Probe which PWM enable values the kernel accepts (read-only where possible).
zenbook_fan_pwm_modes_available() {
	local hwmon enable cur
	hwmon="$(zenbook_fan_find_hwmon)" || return 1
	enable="${hwmon}/pwm1_enable"
	[[ -e "${enable}" ]] || {
		echo "pwm1_enable: absent (RPM-only)"
		return 0
	}
	cur="$(tr -d '[:space:]' <"${enable}")"
	# On ASUS Zenbooks we know 0/2 work; 1 returns EINVAL — report without writing.
	printf 'pwm_enable path: %s (current=%s)\n' "${enable}" "${cur}"
	printf 'pwm modes:\n'
	printf '  full  (0)  — force max fans (loud)\n'
	printf '  auto  (2)  — firmware thermal curve (default)\n'
	printf '  manual(1)  — NOT available on this model\n'
	if [[ -e "${hwmon}/pwm1_auto_point1_temp" ]]; then
		printf 'custom curves: yes (pwm*_auto_point_*)\n'
	else
		printf 'custom curves: no\n'
	fi
}

zenbook_fan_modes() {
	local hwmon pwm_en profile
	hwmon="$(zenbook_fan_find_hwmon)" || {
		echo "No asus/pwm fan hwmon found" >&2
		return 1
	}
	pwm_en="$(zenbook_fan_pwm_enable_get)"
	printf '=== fan / thermal modes on this machine ===\n'
	printf 'hwmon:     %s\n' "${hwmon}"
	printf '\nPWM (platform-fan auto|full):\n'
	printf '  * auto  — pwm1_enable=2  [current=%s]\n' "$(zenbook_fan_pwm_mode_name "${pwm_en}")"
	printf '  * full  — pwm1_enable=0  (max RPM; loud)\n'
	printf '  - manual curves — not supported\n'
	printf '\nPlatform profiles (platform-fan quiet|balanced|performance):\n'
	if zenbook_platform_profile_present 2>/dev/null; then
		profile="$(zenbook_platform_profile_get)"
		while IFS= read -r p; do
			[[ -n "${p}" ]] || continue
			if [[ "${p}" == "${profile}" ]]; then
				printf '  * %s  [current]\n' "${p}"
			else
				printf '  * %s\n' "${p}"
			fi
		done < <(zenbook_platform_profile_list)
	else
		printf '  (no /sys/firmware/acpi/platform_profile)\n'
	fi
	printf '\nTip: after full → platform-fan auto   (or platform-fan balanced)\n'
}
