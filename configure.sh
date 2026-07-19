#!/usr/bin/env bash
# Lightweight bash configurator (uses whiptail when available).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/zenbook-scripts"
CONFIG_FILE="${CONFIG_DIR}/zenbook-duo.conf"
EXAMPLE="${SCRIPT_DIR}/zenbook-duo.conf.example"

DEFAULTS=0
ALL_YES=0
INCLUDE_FAN=""
PY_EXTRA=()
for arg in "$@"; do
    case "$arg" in
        --defaults) DEFAULTS=1; PY_EXTRA+=("$arg") ;;
        --all-yes) ALL_YES=1; PY_EXTRA+=("$arg") ;;
        --include-fan-control) INCLUDE_FAN=1; PY_EXTRA+=("$arg") ;;
        --no-include-fan-control) INCLUDE_FAN=0; PY_EXTRA+=("$arg") ;;
        --cleanup-usr-local|--cleanup-dry-run) PY_EXTRA+=("$arg") ;;
        --prefix)
            # consumed with next arg below — handled in second pass
            ;;
        --prefix=*)
            PY_EXTRA+=("$arg")
            ;;
        *)
            if [[ "${PREV:-}" == "--prefix" ]]; then
                PY_EXTRA+=(--prefix "$arg")
                PREV=""
                continue
            fi
            echo "Unknown option: $arg" >&2
            echo "Usage: $0 [--defaults] [--all-yes] [--prefix DIR] [--include-fan-control|--no-include-fan-control] [--cleanup-usr-local]" >&2
            exit 2
            ;;
    esac
    PREV="$arg"
done

mkdir -p "${CONFIG_DIR}"
if [[ ! -f "${CONFIG_FILE}" && -f "${EXAMPLE}" ]]; then
    cp "${EXAMPLE}" "${CONFIG_FILE}"
fi

if ! command -v whiptail >/dev/null 2>&1; then
    echo "whiptail not found; falling back to configure.py"
    exec python3 "${SCRIPT_DIR}/configure.py" "${PY_EXTRA[@]}"
fi

if [[ "$DEFAULTS" -eq 1 ]]; then
    USB_VENDOR="0b05"
    USB_PRODUCT="1b2c"
    BT_PRODUCT="1b2d"
    DEFAULT_BRIGHTNESS="1"
else
    USB_VENDOR="$(whiptail --inputbox "USB vendor ID (pogo pins)" 8 60 "0b05" 3>&1 1>&2 2>&3)"
    USB_PRODUCT="$(whiptail --inputbox "USB product ID" 8 60 "1b2c" 3>&1 1>&2 2>&3)"
    BT_PRODUCT="$(whiptail --inputbox "Bluetooth product ID" 8 60 "1b2d" 3>&1 1>&2 2>&3)"
    DEFAULT_BRIGHTNESS="$(whiptail --inputbox "Default brightness 0-3" 8 60 "1" 3>&1 1>&2 2>&3)"
fi

cat > "${CONFIG_FILE}" <<EOF
[keyboard]
usb_vendor_id = ${USB_VENDOR}
usb_product_id = ${USB_PRODUCT}
bt_vendor_id = 0b05
bt_product_id = ${BT_PRODUCT}
usb_windex = 4
default_brightness = ${DEFAULT_BRIGHTNESS}

[duo]
default_backlight = ${DEFAULT_BRIGHTNESS}
default_scale = 1
EOF

echo "Wrote ${CONFIG_FILE}"
if [[ "$ALL_YES" -eq 1 ]]; then
    "${SCRIPT_DIR}/bin/kb-brightness" "${DEFAULT_BRIGHTNESS}" || true
else
    if whiptail --yesno "Test brightness now?" 7 50; then
        "${SCRIPT_DIR}/bin/kb-brightness" "${DEFAULT_BRIGHTNESS}"
    fi
fi

# Interactive fan-control prompt when not already set by CLI flags
if [[ -z "${INCLUDE_FAN}" && "$ALL_YES" -eq 0 ]]; then
    if whiptail --yesno "Include adaptive fan-control daemon?" 8 60; then
        PY_EXTRA+=(--include-fan-control)
    else
        PY_EXTRA+=(--no-include-fan-control)
    fi
fi

if [[ "$ALL_YES" -eq 1 ]]; then
    # Ensure --defaults/--all-yes even if only fan flags were passed
    has_defaults=0
    has_all_yes=0
    for a in "${PY_EXTRA[@]+"${PY_EXTRA[@]}"}"; do
        [[ "$a" == "--defaults" ]] && has_defaults=1
        [[ "$a" == "--all-yes" ]] && has_all_yes=1
    done
    [[ "$has_defaults" -eq 0 ]] && PY_EXTRA+=(--defaults)
    [[ "$has_all_yes" -eq 0 ]] && PY_EXTRA+=(--all-yes)
    exec python3 "${SCRIPT_DIR}/configure.py" "${PY_EXTRA[@]}"
else
    if whiptail --yesno "Run full installer (udev + hotkey service)?" 8 70; then
        exec python3 "${SCRIPT_DIR}/configure.py" "${PY_EXTRA[@]}"
    elif [[ "${INCLUDE_FAN}" == "1" ]] || printf '%s\n' "${PY_EXTRA[@]+"${PY_EXTRA[@]}"}" | grep -qx -- '--include-fan-control'; then
        exec python3 "${SCRIPT_DIR}/configure.py" --defaults --include-fan-control
    fi
fi
