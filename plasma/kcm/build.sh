#!/usr/bin/env bash
# Build and install kcm_zenbook_platform (Plasma 6 / KF6).
#
# User install (default, no root):
#   ./build.sh
#   kcmshell6 kcm_zenbook_platform
#
# System install:
#   PREFIX=/usr ./build.sh --system
#   # or: sudo ./build.sh --system
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$ROOT/../.." && pwd)"
BUILD="${BUILD:-$ROOT/build}"
PREFIX="${PREFIX:-$HOME/.local}"
SYSTEM=0

for arg in "$@"; do
	case "$arg" in
		--system) SYSTEM=1; PREFIX=/usr ;;
		-h|--help)
			sed -n '2,12p' "$0"
			exit 0
			;;
	esac
done

mkdir -p "$BUILD"

SCRIPTS_ROOT="/usr/share/zenbook-scripts"
if [[ "$SYSTEM" -eq 0 ]]; then
	# Dev install may fall back to the checkout for unresolved CLIs.
	SCRIPTS_ROOT="$REPO_ROOT"
fi

cmake -B "$BUILD" \
	-DCMAKE_BUILD_TYPE=RelWithDebInfo \
	-DCMAKE_INSTALL_PREFIX="$PREFIX" \
	-DZENBOOK_SCRIPTS_ROOT="$SCRIPTS_ROOT"

cmake --build "$BUILD" -j"$(nproc 2>/dev/null || echo 2)"

if [[ "$SYSTEM" -eq 1 && "$PREFIX" == /usr && "$(id -u)" -ne 0 ]]; then
	echo "Installing to /usr requires root; re-run with sudo or use default ~/.local install." >&2
	echo "  sudo env PREFIX=/usr $0 --system" >&2
	exit 1
fi

cmake --install "$BUILD"

echo
echo "Installed kcm_zenbook_platform to prefix: $PREFIX"
echo "Plugin: $PREFIX/lib64/qt6/plugins/plasma/kcms/systemsettings/kcm_zenbook_platform.so"
echo "        (or $PREFIX/lib64/plugins/... on some distros)"
echo "Desktop: $PREFIX/share/applications/kcm_zenbook_platform.desktop"
echo
echo "System Settings → Display & Monitor → ZenBook Platform"
echo "Or: kcmshell6 kcm_zenbook_platform"
