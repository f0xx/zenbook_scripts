# shellcheck shell=bash
# Fn-lock Mode A/B persistence for UX8406 sideloaded hid-asus.
#
# Mode A: fn_lock=1 (plain F-keys)
# Mode B: fn_lock=0 (Fn layer — Fn+F4 backlight, etc.)

ZENBOOK_KB_FN_LOCK_STATE_FILE="${ZENBOOK_KB_CONFIG_DIR}/fn-lock-mode"
ZENBOOK_KB_FN_LOCK_TOGGLED_FILE="${ZENBOOK_KB_CONFIG_DIR}/fn-lock-toggled"

zenbook_kb_fn_lock_mark_toggled() {
    mkdir -p "$(dirname "${ZENBOOK_KB_FN_LOCK_TOGGLED_FILE}")"
    date -u +%Y-%m-%dT%H:%M:%SZ > "${ZENBOOK_KB_FN_LOCK_TOGGLED_FILE}"
}

zenbook_kb_fn_lock_toggled_recently() {
    [[ -f "${ZENBOOK_KB_FN_LOCK_TOGGLED_FILE}" ]]
}

zenbook_kb_fn_lock_clear_toggled() {
    rm -f "${ZENBOOK_KB_FN_LOCK_TOGGLED_FILE}"
}

zenbook_kb_fn_lock_desired() {
    local path="${1:-${ZENBOOK_KB_DEFAULT_SNAPSHOT}}"
    local fn_lock

    if zenbook_kb_fn_lock_toggled_recently \
        && fn_lock="$(zenbook_kb_fn_lock_state_read 2>/dev/null)"; then
        printf '%s' "${fn_lock}"
        return 0
    fi

    if [[ -f "${path}" ]]; then
        fn_lock="$(zenbook_kb_snapshot_read_value "${path}" fn_lock 2>/dev/null || true)"
        if [[ "${fn_lock}" =~ ^[01]$ ]]; then
            printf '%s' "${fn_lock}"
            return 0
        fi
    fi

    if fn_lock="$(zenbook_kb_fn_lock_state_read 2>/dev/null)"; then
        printf '%s' "${fn_lock}"
        return 0
    fi

    zenbook_kb_fn_lock_conf_default
}

zenbook_kb_fn_lock_mode_name() {
    local fn_lock="$1"
    if [[ "${fn_lock}" == "1" ]]; then
        printf 'A'
    else
        printf 'B'
    fi
}

zenbook_kb_fn_lock_conf_default() {
    local val="${fn_lock_default:-}"
    if [[ -z "${val}" && -f /etc/conf.d/zenbook-kb-hid-asus ]]; then
        # shellcheck disable=SC1091
        source /etc/conf.d/zenbook-kb-hid-asus
        val="${fn_lock_default:-}"
    fi
    case "${val}" in
        1|true|yes|A|a) printf '1' ;;
        0|false|no|B|b) printf '0' ;;
        *) printf '0' ;;
    esac
}

zenbook_kb_fn_lock_state_read() {
    local raw
    if [[ -r "${ZENBOOK_KB_FN_LOCK_STATE_FILE}" ]]; then
        raw="$(tr -d '[:space:]' < "${ZENBOOK_KB_FN_LOCK_STATE_FILE}")"
        case "${raw}" in
            0|1) printf '%s' "${raw}"; return 0 ;;
            A|a) printf '1'; return 0 ;;
            B|b) printf '0'; return 0 ;;
        esac
    fi
    return 1
}

zenbook_kb_fn_lock_state_write() {
    local fn_lock="$1"
    local owner_home
    mkdir -p "$(dirname "${ZENBOOK_KB_FN_LOCK_STATE_FILE}")"
    printf '%s\n' "${fn_lock}" > "${ZENBOOK_KB_FN_LOCK_STATE_FILE}"
    if [[ "$(id -u)" -eq 0 ]]; then
        owner_home="$(zenbook_kb_user_home)"
        if [[ -n "${owner_home}" && -d "${owner_home}" ]]; then
            chown "$(stat -c '%u:%g' "${owner_home}")" "${ZENBOOK_KB_FN_LOCK_STATE_FILE}" 2>/dev/null || true
        fi
    fi
}

zenbook_kb_fn_lock_vendor_hidraw() {
    local hidraw uevent size

    for hidraw in /sys/class/hidraw/hidraw*; do
        [[ -d "${hidraw}" ]] || continue
        uevent="${hidraw}/device/uevent"
        [[ -r "${uevent}" ]] || continue
        if ! zenbook_kb_hid_id_matches "${uevent}" "${ZENBOOK_KB_USB_VENDOR_ID}" "${ZENBOOK_KB_USB_PRODUCT_ID}"; then
            continue
        fi
        size="$(wc -c < "${hidraw}/device/report_descriptor")"
        if [[ "${size}" -lt 90 || "${size}" -gt 120 ]]; then
            continue
        fi
        echo "/dev/$(basename "${hidraw}")"
        return 0
    done
    return 1
}

zenbook_kb_fn_lock_hidraw_read() {
    local hidraw="$1"

    if [[ ! -r "${hidraw}" && "${EUID}" -ne 0 ]]; then
        return 1
    fi

    python3 - "${hidraw}" <<'PY'
import fcntl
import os
import sys

hidraw = sys.argv[1]
fd = os.open(hidraw, os.O_RDWR)
buf = bytearray(64)
buf[0:4] = [0x5A, 0xD0, 0x4E, 0]
fcntl.ioctl(fd, 0xC0094807, buf)  # HIDIOCGFEATURE(64)
os.close(fd)
if buf[0] != 0x5A or buf[1] != 0xD0 or buf[2] != 0x4E:
    raise SystemExit(1)
print(int(bool(buf[3])))
PY
}

zenbook_kb_fn_lock_hidraw_read_primed() {
    local hidraw="$1" guess="$2" fn_lock

    if fn_lock="$(zenbook_kb_fn_lock_hidraw_read "${hidraw}" 2>/dev/null)"; then
        printf '%s' "${fn_lock}"
        return 0
    fi
    if [[ ! "${guess}" =~ ^[01]$ ]]; then
        return 1
    fi
    zenbook_kb_fn_lock_hidraw_apply "${hidraw}" "${guess}" 2>/dev/null || return 1
    zenbook_kb_fn_lock_hidraw_read "${hidraw}"
}

zenbook_kb_fn_lock_reload_kind() {
    local kind_file="/run/zenbook-hid-asus/reload-kind"
    if [[ -r "${kind_file}" ]]; then
        tr -d '[:space:]' < "${kind_file}"
        return 0
    fi
    printf 'full'
}

zenbook_kb_fn_lock_hidraw_apply() {
    local hidraw="$1"
    local fn_lock="$2"

    if [[ ! -w "${hidraw}" && "${EUID}" -ne 0 ]]; then
        echo "Permission denied for ${hidraw}; run with sudo" >&2
        return 1
    fi

    python3 - "${hidraw}" "${fn_lock}" <<'PY'
import fcntl
import os
import sys

hidraw = sys.argv[1]
enabled = 1 if int(sys.argv[2]) else 0
fd = os.open(hidraw, os.O_RDWR)
buf = bytearray(64)
buf[0:4] = [0x5A, 0xD0, 0x4E, enabled]
fcntl.ioctl(fd, 0xC0094806, buf)  # HIDIOCSFEATURE(64)
os.close(fd)
PY
}

zenbook_kb_fn_lock_read_for_save() {
    local path="${1:-${ZENBOOK_KB_DEFAULT_SNAPSHOT}}"
    local hidraw fn_lock existing

    if [[ -f "${path}" ]]; then
        existing="$(zenbook_kb_snapshot_read_value "${path}" fn_lock 2>/dev/null || true)"
    fi

    if zenbook_kb_usb_present && hidraw="$(zenbook_kb_fn_lock_vendor_hidraw)"; then
        if fn_lock="$(zenbook_kb_fn_lock_hidraw_read "${hidraw}" 2>/dev/null)"; then
            zenbook_kb_fn_lock_state_write "${fn_lock}"
            zenbook_kb_fn_lock_clear_toggled
            printf '%s' "${fn_lock}"
            return 0
        fi
    fi

    if zenbook_kb_fn_lock_toggled_recently \
        && fn_lock="$(zenbook_kb_fn_lock_state_read 2>/dev/null)"; then
        printf '%s' "${fn_lock}"
        return 0
    fi

    if [[ "${existing}" =~ ^[01]$ ]]; then
        printf '%s' "${existing}"
        return 0
    fi

    if fn_lock="$(zenbook_kb_fn_lock_state_read 2>/dev/null)"; then
        printf '%s' "${fn_lock}"
        return 0
    fi

    zenbook_kb_fn_lock_conf_default
}

zenbook_kb_fn_lock_read_current() {
    local hidraw fn_lock guess

    if zenbook_kb_usb_present; then
        if hidraw="$(zenbook_kb_fn_lock_vendor_hidraw)"; then
            guess="$(zenbook_kb_fn_lock_state_read 2>/dev/null || zenbook_kb_fn_lock_conf_default)"
            if fn_lock="$(zenbook_kb_fn_lock_hidraw_read_primed "${hidraw}" "${guess}" 2>/dev/null)"; then
                zenbook_kb_fn_lock_state_write "${fn_lock}"
                printf '%s' "${fn_lock}"
                return 0
            fi
        fi
    fi

    if fn_lock="$(zenbook_kb_fn_lock_state_read 2>/dev/null)"; then
        printf '%s' "${fn_lock}"
        return 0
    fi

    if [[ -f "${ZENBOOK_KB_DEFAULT_SNAPSHOT}" ]]; then
        fn_lock="$(zenbook_kb_snapshot_read_value "${ZENBOOK_KB_DEFAULT_SNAPSHOT}" fn_lock 2>/dev/null || true)"
        if [[ "${fn_lock}" =~ ^[01]$ ]]; then
            printf '%s' "${fn_lock}"
            return 0
        fi
    fi

    zenbook_kb_fn_lock_conf_default
}

zenbook_kb_fn_lock_apply() {
    local fn_lock="${1:-}"

    if [[ ! "${fn_lock}" =~ ^[01]$ ]]; then
        echo "Invalid fn_lock value: ${fn_lock}" >&2
        return 1
    fi

    # Fn-lock key mapping lives in the kernel driver (drvdata->fn_lock).
    # HID feature SET from userspace updates firmware only and can desync
    # from the driver's idea of the mode.  Use insmod fn_lock_default instead.
    zenbook_kb_fn_lock_state_write "${fn_lock}"
    printf '%s' "${fn_lock}"
}

zenbook_kb_fn_lock_toggle_state() {
    local cur next
    cur="$(zenbook_kb_fn_lock_state_read 2>/dev/null || zenbook_kb_fn_lock_conf_default)"
    if [[ "${cur}" == "1" ]]; then
        next=0
    else
        next=1
    fi
    zenbook_kb_fn_lock_mark_toggled
    zenbook_kb_fn_lock_state_write "${next}"
}

zenbook_kb_fn_lock_sync() {
    zenbook_kb_fn_lock_restore
}

zenbook_kb_fn_lock_restore() {
    local path="${1:-${ZENBOOK_KB_DEFAULT_SNAPSHOT}}"
    local fn_lock hidraw

    fn_lock="$(zenbook_kb_fn_lock_desired "${path}")"
    [[ "${fn_lock}" =~ ^[01]$ ]] || return 1

    zenbook_kb_fn_lock_state_write "${fn_lock}"

    if ! zenbook_kb_usb_present; then
        printf '%s' "${fn_lock}"
        return 0
    fi

    hidraw="$(zenbook_kb_fn_lock_vendor_hidraw)" || return 0
    zenbook_kb_fn_lock_hidraw_apply "${hidraw}" "${fn_lock}" 2>/dev/null || return 1
    printf '%s' "${fn_lock}"
}

zenbook_kb_fn_lock_insmod_default() {
    local path="${1:-${ZENBOOK_KB_DEFAULT_SNAPSHOT}}"
    local fn_lock

    if zenbook_kb_fn_lock_toggled_recently \
        && fn_lock="$(zenbook_kb_fn_lock_state_read 2>/dev/null)"; then
        printf '%s' "${fn_lock}"
        return 0
    fi

    if [[ -f "${path}" ]]; then
        fn_lock="$(zenbook_kb_snapshot_read_value "${path}" fn_lock 2>/dev/null || true)"
        if [[ "${fn_lock}" =~ ^[01]$ ]]; then
            printf '%s' "${fn_lock}"
            return 0
        fi
    fi
    if fn_lock="$(zenbook_kb_fn_lock_state_read 2>/dev/null)"; then
        printf '%s' "${fn_lock}"
        return 0
    fi
    zenbook_kb_fn_lock_conf_default
}

zenbook_kb_fn_lock_needs_full_reload() {
    # Kernel fn-lock only resets on insmod/probe — not via userspace HID SET.
    zenbook_kb_fn_lock_toggled_recently || [[ "${ZENBOOK_HID_FORCE_FN_LOCK_RELOAD:-1}" == "1" ]]
}
