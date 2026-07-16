# ACPI platform_profile helpers (quiet / balanced / performance on ASUS WMI).

ZENBOOK_PLATFORM_PROFILE="${ZENBOOK_PLATFORM_PROFILE:-/sys/firmware/acpi/platform_profile}"
ZENBOOK_PLATFORM_PROFILE_CHOICES="${ZENBOOK_PLATFORM_PROFILE_CHOICES:-/sys/firmware/acpi/platform_profile_choices}"

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

zenbook_platform_profile_write() {
	local value="$1"
	if [[ -w "${ZENBOOK_PLATFORM_PROFILE}" ]]; then
		printf '%s\n' "${value}" >"${ZENBOOK_PLATFORM_PROFILE}"
		return 0
	fi
	if command -v sudo >/dev/null 2>&1; then
		printf '%s\n' "${value}" | sudo tee "${ZENBOOK_PLATFORM_PROFILE}" >/dev/null
		return 0
	fi
	echo "Cannot write ${ZENBOOK_PLATFORM_PROFILE} (need root)" >&2
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
	zenbook_platform_profile_get
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
