# shellcheck shell=bash
# Bluetooth transport using hidraw HID feature reports.

zenbook_kb_bluetooth_set_brightness() {
    local level="$1"
    local hidraw

    hidraw="$(zenbook_kb_resolve_hidraw bluetooth)" || {
        echo "Bluetooth keyboard hidraw device not found" >&2
        return 1
    }
    zenbook_kb_hidraw_set_brightness "${hidraw}" "${level}"
}
