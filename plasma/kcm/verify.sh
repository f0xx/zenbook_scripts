#!/usr/bin/env bash
# Smoke-test kcm_zenbook_platform QML load (stderr only).
# Run after build/install. Exits non-zero if QML errors appear.
set -euo pipefail

PLUGIN="/usr/lib64/qt6/plugins/plasma/kcms/systemsettings/kcm_zenbook_platform.so"
if [[ ! -f "$PLUGIN" ]]; then
	PLUGIN="${HOME}/.local/lib64/qt6/plugins/plasma/kcms/systemsettings/kcm_zenbook_platform.so"
fi
if [[ ! -f "$PLUGIN" ]]; then
	echo "kcm_zenbook_platform.so not found under /usr or ~/.local" >&2
	exit 1
fi

echo "plugin: $PLUGIN ($(stat -c '%y' "$PLUGIN"))"

# Longer window: all tab pages load at KCM open (StackLayout, active loaders).
LOG="$(mktemp)"
timeout 8 kcmshell6 kcm_zenbook_platform 2>"$LOG" &
pid=$!
sleep 6
kill "$pid" 2>/dev/null || true
wait "$pid" 2>/dev/null || true

PATTERN='error|failed|Unable to assign|ReferenceError|Cannot assign|helpText|KCM page failed'
if rg -i "$PATTERN" "$LOG"; then
	echo "--- full stderr ---" >&2
	cat "$LOG" >&2
	rm -f "$LOG"
	exit 1
fi

rm -f "$LOG"
echo "OK: no QML errors in 6s launch capture"
