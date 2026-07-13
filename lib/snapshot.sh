# shellcheck shell=bash
# Save and restore keyboard settings snapshots.

ZENBOOK_KB_DEFAULT_SNAPSHOT="${ZENBOOK_KB_CONFIG_DIR}/zenbook_duo.save"

zenbook_kb_snapshot_write() {
    local path="${1:-${ZENBOOK_KB_DEFAULT_SNAPSHOT}}"
    local brightness min max

    zenbook_kb_limits_load_config
    brightness="$(zenbook_kb_state_read 1)"
    min="$(zenbook_kb_get_min)"
    max="$(zenbook_kb_get_max)"
    mkdir -p "$(dirname "${path}")"

    cat > "${path}" <<EOF
[keyboard]
version = 1
saved_at = $(date -u +%Y-%m-%dT%H:%M:%SZ)
brightness = ${brightness}
usb_vendor_id = ${ZENBOOK_KB_USB_VENDOR_ID}
usb_product_id = ${ZENBOOK_KB_USB_PRODUCT_ID}
bt_vendor_id = ${ZENBOOK_KB_BT_VENDOR_ID}
bt_product_id = ${ZENBOOK_KB_BT_PRODUCT_ID}
usb_windex = ${ZENBOOK_KB_USB_WINDEX}
default_brightness = ${brightness}
brightness_min = ${min}
brightness_max = ${max}
EOF
    echo "${path}"
}

zenbook_kb_snapshot_read_value() {
    local path="$1" key="$2"
    grep -E "^${key} *= *" "${path}" | head -n1 | sed 's/^[^=]*= *//'
}

zenbook_kb_snapshot_update_config() {
    local path="$1" key value

    [[ -f "${ZENBOOK_KB_CONFIG_FILE}" ]] || mkdir -p "$(dirname "${ZENBOOK_KB_CONFIG_FILE}")"

    for key in usb_vendor_id usb_product_id bt_vendor_id bt_product_id usb_windex default_brightness brightness_min brightness_max; do
        value="$(zenbook_kb_snapshot_read_value "${path}" "${key}" || true)"
        [[ -n "${value}" ]] || continue
        if grep -q "^${key} *=" "${ZENBOOK_KB_CONFIG_FILE}" 2>/dev/null; then
            sed -i "s/^${key} *= *.*/${key} = ${value}/" "${ZENBOOK_KB_CONFIG_FILE}"
        else
            if ! grep -q '^\[keyboard\]' "${ZENBOOK_KB_CONFIG_FILE}" 2>/dev/null; then
                printf '[keyboard]\n' >> "${ZENBOOK_KB_CONFIG_FILE}"
            fi
            printf '%s = %s\n' "${key}" "${value}" >> "${ZENBOOK_KB_CONFIG_FILE}"
        fi
    done
}

zenbook_kb_snapshot_restore() {
    local path="${1:-${ZENBOOK_KB_DEFAULT_SNAPSHOT}}"

    if [[ ! -f "${path}" ]]; then
        echo "Snapshot not found: ${path}" >&2
        return 1
    fi

    local brightness
    brightness="$(zenbook_kb_snapshot_read_value "${path}" brightness)"
    if [[ ! "${brightness}" =~ ^[0-9]+$ ]]; then
        echo "Invalid brightness in snapshot: ${path}" >&2
        return 1
    fi

    zenbook_kb_snapshot_update_config "${path}"
    zenbook_kb_state_write "${brightness}"
    echo "${brightness}"
}

zenbook_kb_apply_brightness() {
    local target="$1"

    ACTIVE_MODE="$(zenbook_kb_detect_mode "${MODE}")" || {
        echo "Zenbook Duo keyboard not found" >&2
        return 1
    }

    case "${ACTIVE_MODE}" in
        usb)
            if ! zenbook_kb_usb_set_brightness "${target}" "${SCRIPT_DIR}" 2>/dev/null; then
                HIDRAW="$(zenbook_kb_resolve_hidraw usb)" || {
                    echo "USB keyboard control interface not found" >&2
                    return 1
                }
                zenbook_kb_hidraw_set_brightness "${HIDRAW}" "${target}"
            fi
            ;;
        bluetooth)
            zenbook_kb_bluetooth_set_brightness "${target}"
            ;;
        *)
            echo "Unknown mode: ${ACTIVE_MODE}" >&2
            return 1
            ;;
    esac

    zenbook_kb_state_write "${target}"
    echo "${target}"
}
