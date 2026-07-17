# shellcheck shell=bash
# USB (pogo-pin) transport using pyusb via bundled brightness.py.

zenbook_kb_usb_set_brightness() {
    local level="$1"
    local script_dir="$2"
    local extra_args=()
    local brightness_py="${script_dir}/brightness.py"
    if [[ ! -f "${brightness_py}" && -f /usr/share/zenbook-scripts/brightness.py ]]; then
        brightness_py=/usr/share/zenbook-scripts/brightness.py
    elif [[ ! -f "${brightness_py}" && -f /usr/local/share/zenbook-scripts/brightness.py ]]; then
        brightness_py=/usr/local/share/zenbook-scripts/brightness.py
    fi

    [[ -n "${ZENBOOK_KB_USB_VENDOR_ID}" ]] && extra_args+=(--vendor-id "0x${ZENBOOK_KB_USB_VENDOR_ID}")
    [[ -n "${ZENBOOK_KB_USB_PRODUCT_ID}" ]] && extra_args+=(--product-id "0x${ZENBOOK_KB_USB_PRODUCT_ID}")
    extra_args+=(--mode usb --quiet)

    python3 "${brightness_py}" "${level}" "${extra_args[@]}"
}
