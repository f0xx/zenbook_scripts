#!/bin/sh
# Build Plasma 6 KCM into Debian package root (DESTDIR).
set -eu

PKGROOT="${1:?usage: build-kcm.sh <debian/zenbook-scripts-plasma>}"
SCRIPT_DIR="$(CDPATH= cd -P "$(dirname "$0")" && pwd)"
REPO_ROOT="$(CDPATH= cd "${SCRIPT_DIR}/../.." && pwd)"
BUILD="${REPO_ROOT}/plasma/kcm/build-deb"

mkdir -p "${PKGROOT}"
rm -rf "${BUILD}"
cmake -B "${BUILD}" \
	-DCMAKE_BUILD_TYPE=RelWithDebInfo \
	-DCMAKE_INSTALL_PREFIX=/usr \
	-DZENBOOK_SCRIPTS_ROOT=/usr/share/zenbook-scripts \
	"${REPO_ROOT}/plasma/kcm"

cmake --build "${BUILD}" -j"$(nproc 2>/dev/null || echo 2)"
DESTDIR="${PKGROOT}" cmake --install "${BUILD}"
echo "Installed KCM into ${PKGROOT}"
