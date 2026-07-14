#!/bin/sh
# acpid helper for lid and sleep buttons.
# Install: /usr/local/libexec/zenbook-kbd-sleep.sh

case "$1" in
    button/lid)
        # LID0 = open, LID1 = closed (common ACPI naming)
        if grep -q 'close' /proc/acpi/button/lid/LID/state 2>/dev/null \
            || grep -q 'closed' /proc/acpi/button/lid/LID/state 2>/dev/null; then
            /usr/local/bin/kb-brightness-sleep lid-close
        else
            /usr/local/bin/kb-brightness-sleep lid-open
        fi
        ;;
    button/sleep|button/suspend)
        /usr/local/bin/kb-brightness-sleep pre
        ;;
    *)
        exit 0
        ;;
esac

exit 0
