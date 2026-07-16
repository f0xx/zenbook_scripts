# shellcheck shell=bash
# Brightness limit helpers.

zenbook_kb_limits_load_config() {
    if [[ -f "${ZENBOOK_KB_CONFIG_FILE}" ]]; then
        # shellcheck disable=SC1090
        source <(grep -E '^brightness_(min|max) *= *' "${ZENBOOK_KB_CONFIG_FILE}" 2>/dev/null | sed 's/ *= */=/' | sed 's/^/ZENBOOK_KB_CFG_/' || true)
        if [[ -n "${ZENBOOK_KB_CFG_brightness_min:-}" ]]; then
            ZENBOOK_KB_BRIGHTNESS_MIN="${ZENBOOK_KB_CFG_brightness_min}"
        fi
        if [[ -n "${ZENBOOK_KB_CFG_brightness_max:-}" ]]; then
            ZENBOOK_KB_BRIGHTNESS_MAX="${ZENBOOK_KB_CFG_brightness_max}"
        fi
    fi
}

zenbook_kb_sysfs_brightness_path() {
    local led="/sys/class/leds/asus::kbd_backlight/brightness"
    if [[ -r "${led}" || -w "${led}" ]]; then
        echo "${led}"
        return 0
    fi
    return 1
}

zenbook_kb_sysfs_read() {
    local path
    path="$(zenbook_kb_sysfs_brightness_path)" || return 1
    tr -d '[:space:]' < "${path}"
}

zenbook_kb_sysfs_set() {
    local level="$1" path
    path="$(zenbook_kb_sysfs_brightness_path)" || return 1
    if [[ ! -w "${path}" ]]; then
        return 1
    fi
    printf '%s\n' "${level}" > "${path}"
}

zenbook_kb_sysfs_max() {
    local max_path="/sys/class/leds/asus::kbd_backlight/max_brightness"
    if [[ -r "${max_path}" ]]; then
        tr -d '[:space:]' < "${max_path}"
        return 0
    fi
    return 1
}

zenbook_kb_get_min() {
    zenbook_kb_limits_load_config
    echo "${ZENBOOK_KB_BRIGHTNESS_MIN}"
}

zenbook_kb_get_max() {
    local sysfs_max

    zenbook_kb_limits_load_config
    if sysfs_max="$(zenbook_kb_sysfs_max)"; then
        echo "${sysfs_max}"
        return 0
    fi
    echo "${ZENBOOK_KB_BRIGHTNESS_MAX}"
}

zenbook_kb_limits_source() {
    if [[ -f "${ZENBOOK_KB_CONFIG_FILE}" ]] && grep -qE '^brightness_(min|max) *=' "${ZENBOOK_KB_CONFIG_FILE}" 2>/dev/null; then
        echo "config"
    elif [[ -r /sys/class/leds/asus::kbd_backlight/max_brightness ]]; then
        echo "sysfs"
    else
        echo "protocol"
    fi
}
