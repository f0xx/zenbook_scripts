# Shared constants for ASUS Zenbook Duo keyboard backlight.
# Protocol: https://openrgb-wiki.readthedocs.io/en/latest/asus/ASUS-Aura-Core/

zenbook_kb_user_home() {
    if [[ -n "${SUDO_USER:-}" ]]; then
        getent passwd "${SUDO_USER}" | cut -d: -f6
        return 0
    fi
    if [[ -n "${ZENBOOK_CALIB_USER:-}" ]]; then
        getent passwd "${ZENBOOK_CALIB_USER}" | cut -d: -f6
        return 0
    fi
    if [[ "$(id -u)" -eq 0 && -r /etc/conf.d/zenbook-kb-hotkeys ]]; then
        local cu
        cu="$(grep -E '^command_user=' /etc/conf.d/zenbook-kb-hotkeys 2>/dev/null | head -1 | sed 's/^command_user=//' | tr -d '"' | cut -d: -f1)"
        if [[ -n "${cu}" && "${cu}" != root ]]; then
            getent passwd "${cu}" | cut -d: -f6
            return 0
        fi
    fi
    printf '%s' "${HOME}"
}

ZENBOOK_KB_REPORT_ID=0x5A
ZENBOOK_KB_BRIGHTNESS_MAX=3
ZENBOOK_KB_BRIGHTNESS_MIN=0

# Pogo-pin USB (Primax detachable keyboard)
ZENBOOK_KB_USB_VENDOR_ID=0b05
ZENBOOK_KB_USB_PRODUCT_ID=1b2c

# Bluetooth when detached
ZENBOOK_KB_BT_VENDOR_ID=0b05
ZENBOOK_KB_BT_PRODUCT_ID=1b2d

# USB HID SET_REPORT interface (pyusb transport)
ZENBOOK_KB_USB_WINDEX=4

# hidraw report descriptor sizes for control interfaces
ZENBOOK_KB_USB_REPORT_DESC_SIZE=90
ZENBOOK_KB_BT_REPORT_DESC_SIZE=257

ZENBOOK_KB_CONFIG_DIR="${XDG_CONFIG_HOME:-$(zenbook_kb_user_home)/.config}/zenbook-scripts"
ZENBOOK_KB_CONFIG_FILE="${ZENBOOK_KB_CONFIG_DIR}/zenbook-duo.conf"
ZENBOOK_KB_STATE_FILE="${ZENBOOK_KB_STATE_DIR:-$ZENBOOK_KB_CONFIG_DIR}/keyboard-brightness"
ZENBOOK_KB_DEFAULT_SNAPSHOT="${ZENBOOK_KB_CONFIG_DIR}/zenbook_duo.save"
