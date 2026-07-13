# shellcheck shell=bash
# Send ASUS keyboard brightness HID feature report via hidraw ioctl.

zenbook_kb_hidraw_set_brightness() {
    local hidraw="$1"
    local level="$2"

    if [[ ! -w "${hidraw}" && "${EUID}" -ne 0 ]]; then
        echo "Permission denied for ${hidraw}; run with sudo" >&2
        return 1
    fi

    python3 - "${hidraw}" "${level}" <<'PY'
import fcntl
import os
import sys

hidraw = sys.argv[1]
level = int(sys.argv[2])
fd = os.open(hidraw, os.O_RDWR)
buf = bytearray(64)
buf[0:5] = [0x5A, 0xBA, 0xC5, 0xC4, level]
# HIDIOCSFEATURE(64) on Linux x86_64
fcntl.ioctl(fd, 0xC0094806, buf)
os.close(fd)
PY
}
