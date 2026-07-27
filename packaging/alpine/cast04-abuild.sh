#!/bin/sh
set -e
. "$HOME/.abuild/abuild.conf"
export SRCDEST="${SRCDEST:-$HOME/aports/distfiles}"
mkdir -p "$SRCDEST" "$HOME/packages"
cd "$HOME/zenbook_scripts"
chmod +x packaging/debian/install.sh
tar -czf "$SRCDEST/main.tar.gz" \
	--transform 's,^,zenbook_scripts-main/,' \
	--exclude=plasma/kcm/build \
	--exclude=.git \
	--exclude=__pycache__ \
	.
SUM="$(sha512sum "$SRCDEST/main.tar.gz" | awk '{print $1}')"
cat > packaging/alpine/APKBUILD <<APKEOF
# Contributor: f0xx <foxx@users.noreply.github.com>
# Maintainer: f0xx <foxx@users.noreply.github.com>
pkgname=zenbook-scripts
pkgver=0.0.3_pre1
pkgrel=0
pkgdesc="ASUS ZenBook Duo keyboard and platform utilities (CLI-first)"
url="https://github.com/f0xx/zenbook_scripts"
arch="noarch"
license="GPL-2.0-or-later"
depends="python3 py3-usb dmidecode"
makedepends=""
options="!check"
source="main.tar.gz"
builddir="\$srcdir/zenbook_scripts-main"

package() {
	"\$builddir/packaging/debian/install.sh" "\$pkgdir"
}

sha512sums="
$SUM  main.tar.gz
"
APKEOF
cd packaging/alpine
abuild -F -r -P "$HOME/packages"
find "$HOME/packages" -name 'zenbook-scripts*.apk' -ls
