#!/bin/sh
# acpid helper for lid and sleep buttons.
# Install: /usr/local/libexec/zenbook-kbd-sleep.sh

zenbook_kb_run_user() {
	if [ -r /etc/conf.d/zenbook-kb-hotkeys ]; then
		grep -E '^command_user=' /etc/conf.d/zenbook-kb-hotkeys 2>/dev/null \
			| head -1 \
			| sed 's/^command_user=//' \
			| tr -d '"' \
			| cut -d: -f1
	fi
}

USER="$(zenbook_kb_run_user)"
if [ -n "$USER" ] && [ "$USER" != root ]; then
	export ZENBOOK_CALIB_USER="$USER"
fi

_lid_state() {
	# Lid state can lag the ACPI button event by a few ms.
	sleep 0.15
	if grep -qiE 'close|closed' /proc/acpi/button/lid/LID/state 2>/dev/null; then
		echo closed
	else
		echo open
	fi
}

case "$1" in
    button/lid)
        if [ "$(_lid_state)" = closed ]; then
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
