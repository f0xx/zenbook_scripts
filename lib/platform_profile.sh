# ACPI platform_profile helpers (quiet / balanced / performance on ASUS WMI).
#
# Desired profile is persisted under /var/lib/zenbook-scripts/ so reboot /
# hibernate / resume can restore firmware defaults (often "quiet").
# Adaptive fan-control must set ZENBOOK_PP_PERSIST=0 so temporary sleep_pre
# powersave does not overwrite the user's choice.

ZENBOOK_PLATFORM_PROFILE="${ZENBOOK_PLATFORM_PROFILE:-/sys/firmware/acpi/platform_profile}"
ZENBOOK_PLATFORM_PROFILE_CHOICES="${ZENBOOK_PLATFORM_PROFILE_CHOICES:-/sys/firmware/acpi/platform_profile_choices}"
ZENBOOK_PLATFORM_PROFILE_STATE_DIR="${ZENBOOK_PLATFORM_PROFILE_STATE_DIR:-/var/lib/zenbook-scripts}"
ZENBOOK_PLATFORM_PROFILE_STATE="${ZENBOOK_PLATFORM_PROFILE_STATE:-${ZENBOOK_PLATFORM_PROFILE_STATE_DIR}/platform-profile}"
ZENBOOK_FAN_PWM_STATE="${ZENBOOK_FAN_PWM_STATE:-${ZENBOOK_PLATFORM_PROFILE_STATE_DIR}/fan-pwm-enable}"

zenbook_platform_profile_present() {
	[[ -f "${ZENBOOK_PLATFORM_PROFILE}" ]]
}

zenbook_platform_profile_get() {
	local value
	value="$(tr -d '[:space:]' <"${ZENBOOK_PLATFORM_PROFILE}")"
	printf '%s\n' "${value}"
}

zenbook_platform_profile_list() {
	if [[ -r "${ZENBOOK_PLATFORM_PROFILE_CHOICES}" ]]; then
		tr -s '[:space:]' '\n' <"${ZENBOOK_PLATFORM_PROFILE_CHOICES}" | sed '/^$/d'
		return 0
	fi
	# Fallback common ASUS set
	printf '%s\n' quiet balanced performance
}

zenbook_platform_profile_state_dir() {
	local dir="${ZENBOOK_PLATFORM_PROFILE_STATE_DIR}"
	if [[ -d "${dir}" ]]; then
		printf '%s\n' "${dir}"
		return 0
	fi
	if mkdir -p "${dir}" 2>/dev/null; then
		chmod 0775 "${dir}" 2>/dev/null || true
		printf '%s\n' "${dir}"
		return 0
	fi
	if command -v sudo >/dev/null 2>&1; then
		if sudo -n mkdir -p "${dir}" 2>/dev/null \
			&& sudo -n chmod 0775 "${dir}" 2>/dev/null; then
			printf '%s\n' "${dir}"
			return 0
		fi
	fi
	return 1
}

zenbook_platform_profile_state_write() {
	local value="$1"
	local file="${ZENBOOK_PLATFORM_PROFILE_STATE}"
	local dir

	dir="$(zenbook_platform_profile_state_dir)" || return 1
	file="${dir}/$(basename "${file}")"
	# Test writability first — a failed `>` prints "Permission denied" even with
	# `2>/dev/null` (that only covers printf's stderr, not the shell redirect).
	if [[ -w "${file}" ]] || { [[ ! -e "${file}" && -w "${dir}" ]]; }; then
		printf '%s\n' "${value}" >"${file}" && return 0
	fi
	if command -v sudo >/dev/null 2>&1; then
		if printf '%s\n' "${value}" | sudo -n tee "${file}" >/dev/null 2>&1; then
			return 0
		fi
	fi
	echo "Cannot persist platform_profile to ${file}" >&2
	return 1
}

zenbook_platform_profile_state_read() {
	local file="${ZENBOOK_PLATFORM_PROFILE_STATE}"
	[[ -r "${file}" ]] || return 1
	tr -d '[:space:]' <"${file}"
}

zenbook_platform_profile_write() {
	local value="$1"
	if [[ -w "${ZENBOOK_PLATFORM_PROFILE}" ]]; then
		printf '%s\n' "${value}" >"${ZENBOOK_PLATFORM_PROFILE}"
		return 0
	fi
	if command -v sudo >/dev/null 2>&1; then
		if printf '%s\n' "${value}" | sudo -n tee "${ZENBOOK_PLATFORM_PROFILE}" >/dev/null 2>&1; then
			return 0
		fi
	fi
	echo "Cannot write ${ZENBOOK_PLATFORM_PROFILE} (need root or NOPASSWD sudo -n)" >&2
	return 1
}

zenbook_platform_profile_set() {
	local want="$1"
	local choice
	local found=0
	while IFS= read -r choice; do
		if [[ "${choice}" == "${want}" ]]; then
			found=1
			break
		fi
	done < <(zenbook_platform_profile_list)
	if (( found == 0 )); then
		echo "Unknown profile '${want}'. Choices: $(zenbook_platform_profile_list | tr '\n' ' ')" >&2
		return 2
	fi
	zenbook_platform_profile_write "${want}" || return 1
	# Persist user/CLI choice unless adaptive fan-control opts out.
	if [[ "${ZENBOOK_PP_PERSIST:-1}" != "0" ]]; then
		zenbook_platform_profile_state_write "${want}" || true
	fi
	zenbook_platform_profile_get
}

zenbook_platform_profile_restore() {
	local want
	if ! zenbook_platform_profile_present; then
		return 0
	fi
	want="$(zenbook_platform_profile_state_read 2>/dev/null || true)"
	if [[ -z "${want}" ]]; then
		echo "platform-profile: no saved state at ${ZENBOOK_PLATFORM_PROFILE_STATE}" >&2
		return 0
	fi
	# Restore must not re-write the state file (already correct).
	ZENBOOK_PP_PERSIST=0 zenbook_platform_profile_set "${want}"
}

zenbook_platform_profile_cycle() {
	local current next choices i n
	current="$(zenbook_platform_profile_get)"
	mapfile -t choices < <(zenbook_platform_profile_list)
	n="${#choices[@]}"
	if (( n == 0 )); then
		echo "No platform_profile choices" >&2
		return 1
	fi
	next="${choices[0]}"
	for (( i = 0; i < n; i++ )); do
		if [[ "${choices[$i]}" == "${current}" ]]; then
			next="${choices[$(( (i + 1) % n ))]}"
			break
		fi
	done
	zenbook_platform_profile_set "${next}"
}
