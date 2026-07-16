# shellcheck shell=bash
# Connection detection for USB (pogo pins) vs Bluetooth.

zenbook_kb_load_config() {
    if [[ -f "${ZENBOOK_KB_CONFIG_FILE}" ]]; then
        # shellcheck disable=SC1090
        source <(grep -E '^[a-z_]+ *= *' "${ZENBOOK_KB_CONFIG_FILE}" | sed 's/ *= */=/' | sed 's/^/ZENBOOK_KB_CFG_/')
        [[ -n "${ZENBOOK_KB_CFG_usb_vendor_id:-}" ]] && ZENBOOK_KB_USB_VENDOR_ID="${ZENBOOK_KB_CFG_usb_vendor_id}"
        [[ -n "${ZENBOOK_KB_CFG_usb_product_id:-}" ]] && ZENBOOK_KB_USB_PRODUCT_ID="${ZENBOOK_KB_CFG_usb_product_id}"
        [[ -n "${ZENBOOK_KB_CFG_bt_vendor_id:-}" ]] && ZENBOOK_KB_BT_VENDOR_ID="${ZENBOOK_KB_CFG_bt_vendor_id}"
        [[ -n "${ZENBOOK_KB_CFG_bt_product_id:-}" ]] && ZENBOOK_KB_BT_PRODUCT_ID="${ZENBOOK_KB_CFG_bt_product_id}"
        [[ -n "${ZENBOOK_KB_CFG_usb_windex:-}" ]] && ZENBOOK_KB_USB_WINDEX="${ZENBOOK_KB_CFG_usb_windex}"
    fi
}

zenbook_kb_usb_present() {
    lsusb 2>/dev/null | grep -qi "${ZENBOOK_KB_USB_VENDOR_ID}:${ZENBOOK_KB_USB_PRODUCT_ID}"
}

zenbook_kb_hid_id_matches() {
    local uevent="$1" vendor="$2" product="$3"
    local hid_id vend prod

    hid_id="$(grep '^HID_ID=' "${uevent}" | cut -d= -f2-)" || return 1
    vend="${hid_id#*:}"
    vend="${vend%%:*}"
    prod="${hid_id##*:}"

    (( 16#${vend} == 16#${vendor} )) && (( 16#${prod} == 16#${product} ))
}

zenbook_kb_find_hidraw() {
  local vendor="$1" product="$2" desc_size="$3"
  local hidraw uevent size

  for hidraw in /sys/class/hidraw/hidraw*; do
    [[ -d "${hidraw}" ]] || continue
    uevent="${hidraw}/device/uevent"
    [[ -r "${uevent}" ]] || continue
    if ! zenbook_kb_hid_id_matches "${uevent}" "${vendor}" "${product}"; then
      continue
    fi
    size="$(wc -c < "${hidraw}/device/report_descriptor")"
    if [[ -n "${desc_size}" && "${size}" != "${desc_size}" ]]; then
      continue
    fi
    echo "/dev/$(basename "${hidraw}")"
    return 0
  done
  return 1
}

zenbook_kb_detect_mode() {
    local forced="${1:-auto}"

    case "${forced}" in
        usb)
            echo "usb"
            return 0
            ;;
        bluetooth|bt)
            echo "bluetooth"
            return 0
            ;;
    esac

    if zenbook_kb_usb_present; then
        echo "usb"
        return 0
    fi

    if zenbook_kb_find_hidraw "${ZENBOOK_KB_BT_VENDOR_ID}" "${ZENBOOK_KB_BT_PRODUCT_ID}" "${ZENBOOK_KB_BT_REPORT_DESC_SIZE}" >/dev/null; then
        echo "bluetooth"
        return 0
    fi

    return 1
}

zenbook_kb_resolve_hidraw() {
    local mode="$1"
    case "${mode}" in
        usb)
            zenbook_kb_find_hidraw "${ZENBOOK_KB_USB_VENDOR_ID}" "${ZENBOOK_KB_USB_PRODUCT_ID}" "${ZENBOOK_KB_USB_REPORT_DESC_SIZE}"
            ;;
        bluetooth)
            zenbook_kb_find_hidraw "${ZENBOOK_KB_BT_VENDOR_ID}" "${ZENBOOK_KB_BT_PRODUCT_ID}" "${ZENBOOK_KB_BT_REPORT_DESC_SIZE}"
            ;;
    esac
}
