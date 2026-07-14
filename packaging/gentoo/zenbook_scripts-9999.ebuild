# Copyright 1999-2026 Gentoo Authors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

inherit git-r3

DESCRIPTION="ASUS Zenbook Duo detachable keyboard brightness and Fn+ hotkeys"
HOMEPAGE="https://github.com/f0xx/zenbook_scripts"
EGIT_REPO_URI="https://github.com/f0xx/zenbook_scripts.git"

LICENSE="GPL-2+"
SLOT="0"
KEYWORDS=""

IUSE="hotkeys kernel qt6 zenbook_ux8406"
REQUIRED_USE=""

RDEPEND="
	>=dev-lang/python-3.10
	hotkeys? ( acpid sys-auth/udev )
	qt6? ( dev-python/pyside6 )
	kernel? ( virtual/dist-kernel )
"
DEPEND="${RDEPEND}"

PDEPEND="dev-python/pyusb"

src_install() {
	insinto /usr/local/share/zenbook-scripts
	doins -r zenbook_kb brightness.py conf.d lib
	doins zenbook-hotkeys.conf.example zenbook-duo.conf.example

	dobin configure.py configure.sh
	dobin bin/kb-brightness bin/kb-brightness-hotkeys
	use hotkeys && dobin bin/kb-calibrate-hotkeys bin/kb-brightness-sleep bin/snapshot-plan-state
	use qt6 && dobin configure_gui.py

	dodoc README.md DEPLOY.md LICENSE kernel/README.md packaging/README.md
}

pkg_postinst() {
	if use hotkeys; then
		"${EPREFIX}/usr/bin/python3" "${EPREFIX}/usr/local/bin/configure.py" --defaults --all-yes || true
	fi
}
