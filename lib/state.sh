# shellcheck shell=bash
# Brightness state helpers (hardware does not expose a reliable read path).

zenbook_kb_state_read() {
    local default="${1:-1}" value
    if value="$(zenbook_kb_sysfs_read 2>/dev/null)" && [[ "${value}" =~ ^[0-9]+$ ]]; then
        echo "${value}"
        return 0
    fi
    if [[ -r "${ZENBOOK_KB_STATE_FILE}" ]]; then
        value="$(tr -d '[:space:]' < "${ZENBOOK_KB_STATE_FILE}")"
        if [[ "${value}" =~ ^[0-9]+$ ]]; then
            echo "${value}"
            return 0
        fi
    fi
    echo "${default}"
}

zenbook_kb_state_write() {
    local level="$1"
    mkdir -p "$(dirname "${ZENBOOK_KB_STATE_FILE}")"
    printf '%s\n' "${level}" > "${ZENBOOK_KB_STATE_FILE}"
}

zenbook_kb_clamp() {
    local level="$1"
    if (( level < ZENBOOK_KB_BRIGHTNESS_MIN )); then
        echo "${ZENBOOK_KB_BRIGHTNESS_MIN}"
    elif (( level > ZENBOOK_KB_BRIGHTNESS_MAX )); then
        echo "${ZENBOOK_KB_BRIGHTNESS_MAX}"
    else
        echo "${level}"
    fi
}
