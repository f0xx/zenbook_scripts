# Copyright 1999-2026 Gentoo Authors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

inherit linux-info

DESCRIPTION="ASUS Zenbook Duo scripts (UX8406 keyboard + UX5400 ScreenPad)"
HOMEPAGE="https://github.com/f0xx/zenbook_scripts"

# Upstream tag v0.0.1_hf1 → Gentoo PV 0.0.1_p1 (_hf is not a legal PMS suffix).
# GitHub archive dir uses the repo name (underscore), not ${PN}.
MY_PN="zenbook_scripts"
MY_PV="0.0.1_hf1"
SRC_URI="https://github.com/f0xx/${MY_PN}/archive/refs/tags/v${MY_PV}.tar.gz -> ${MY_PN}-${MY_PV}.tar.gz"
S="${WORKDIR}/${MY_PN}-${MY_PV}"

LICENSE="GPL-2+"
SLOT="0"
KEYWORDS="~amd64"

IUSE="+hotkeys +kernel qt6 screenpad +zenbook_ux8406"
REQUIRED_USE="kernel? ( zenbook_ux8406 )"

RDEPEND="
	>=dev-lang/python-3.10
	dev-python/pyusb
	hotkeys? (
		virtual/udev
		sys-power/acpid
		sys-auth/elogind
	)
	screenpad? (
		virtual/udev
	)
	qt6? ( dev-python/pyside:6 )
"
# Build oot hid-asus against whatever provides /usr/src/linux (gentoo-sources,
# etc.). Do NOT depend on virtual/dist-kernel — that forces gentoo-kernel and
# unrelated USE fights (secureboot/modules-sign) for source-based kernels.
DEPEND="
	${RDEPEND}
	kernel? (
		virtual/linux-sources
		dev-build/make
	)
"

ZENBOOK_SHARE=/usr/local/share/zenbook-scripts
ZENBOOK_LIBEXEC=/usr/local/libexec
ZENBOOK_KO_ROOT=/usr/lib/modules/zenbook-hid-asus

pkg_setup() {
	if use kernel; then
		linux-info_pkg_setup
	fi
}

src_compile() {
	if use kernel; then
		emake -C "${S}/kernel" build-current \
			KDIR="${KERNEL_SRC_PATH:-${ESYSROOT}/lib/modules/${KV_FULL}/build}"
	fi
}

src_install() {
	# Python + shell support tree
	insinto "${ZENBOOK_SHARE}"
	doins -r zenbook_kb brightness.py lib
	doins zenbook-hotkeys.conf.example zenbook-duo.conf.example

	if use zenbook_ux8406; then
		insinto "${ZENBOOK_SHARE}/conf.d"
		doins conf.d/00-default.evdev.conf
		for f in conf.d/UX8406*.evdev.conf conf.d/UX8406*.usb.conf; do
			[[ -f "${S}/${f}" ]] || continue
			doins "${f}"
		done
	fi

	# User-facing CLIs
	dobin configure.py configure.sh bin/kb-brightness bin/kb-platform-profile
	if use screenpad || use hotkeys; then
		dobin bin/screenpad bin/screenpad-boot bin/screenpad-sync
	fi
	if use hotkeys; then
		dobin \
			bin/kb-brightness-hotkeys \
			bin/kb-brightness-sleep \
			bin/kb-brightness-lid-watch \
			bin/kb-calibrate-hotkeys \
			bin/snapshot-plan-state
	fi
	use qt6 && dobin configure_gui.py

	if use hotkeys; then
		insinto "${ZENBOOK_LIBEXEC}"
		newins contrib/udev/zenbook-kb-hotkeys-udev zenbook-kb-hotkeys-udev
		newins contrib/acpi/zenbook-kbd-sleep.sh zenbook-kbd-sleep.sh
		fperms 0755 \
			"${ED}${ZENBOOK_LIBEXEC}/zenbook-kb-hotkeys-udev" \
			"${ED}${ZENBOOK_LIBEXEC}/zenbook-kbd-sleep.sh"

		insinto /etc/udev/rules.d
		doins contrib/udev/99-zenbook-kb-hotkeys.rules

		insinto /etc/acpi/events
		doins contrib/acpi/events/zenbook-kbd-sleep

		insinto /usr/lib/systemd/system-sleep
		newins contrib/systemd/zenbook-kb-brightness-sleep zenbook-kb-brightness
		fperms 0755 "${ED}/usr/lib/systemd/system-sleep/zenbook-kb-brightness"

		newinitd contrib/openrc/zenbook-kb-hotkeys zenbook-kb-hotkeys
		newinitd contrib/openrc/zenbook-kb-lid zenbook-kb-lid

		insinto /etc/modprobe.d
		doins contrib/modprobe/zenbook-hid-asus.conf
	fi

	if use screenpad; then
		insinto /etc/udev/rules.d
		doins contrib/udev/99-zenbook-screenpad.rules

		newinitd contrib/openrc/zenbook-screenpad zenbook-screenpad
		newinitd contrib/openrc/zenbook-screenpad-sync zenbook-screenpad-sync
		newconfd contrib/openrc/conf.d/zenbook-screenpad zenbook-screenpad

		insinto /etc/systemd/system
		doins contrib/systemd/zenbook-screenpad.service
		doins contrib/systemd/zenbook-screenpad-sync.service
	fi

	if use kernel; then
		insinto "${ZENBOOK_LIBEXEC}"
		newins kernel/scripts/switch-hid-asus.sh zenbook-hid-asus-switch
		newins kernel/scripts/rebind-hid-asus.sh zenbook-hid-asus-rebind
		newins contrib/openrc/zenbook-hid-asus-boot.sh zenbook-hid-asus-boot.sh
		fperms 0755 \
			"${ED}${ZENBOOK_LIBEXEC}/zenbook-hid-asus-switch" \
			"${ED}${ZENBOOK_LIBEXEC}/zenbook-hid-asus-rebind" \
			"${ED}${ZENBOOK_LIBEXEC}/zenbook-hid-asus-boot.sh"

		newinitd contrib/openrc/zenbook-kb-hid-asus zenbook-kb-hid-asus
		newconfd contrib/openrc/conf.d/zenbook-kb-hid-asus zenbook-kb-hid-asus

		local ko="${S}/kernel/build/linux-${KV_FULL}/hid-asus.ko"
		[[ -f "${ko}" ]] || die "missing built module: ${ko}"
		insinto "${ZENBOOK_KO_ROOT}/${KV_FULL}"
		doins "${ko}"
	fi

	local doc
	for doc in LICENSE DEPLOY.md README.ux8406.md README.ux5400.md \
		kernel/README.md packaging/README.md PLANNED.md README.md; do
		[[ -f "${S}/${doc}" ]] || continue
		dodoc "${doc}"
	done
}

pkg_postinst() {
	if use hotkeys; then
		"${ROOT}${EPREFIX}/usr/bin/python3" \
			"${ROOT}${EPREFIX}/usr/local/bin/configure.py" --defaults --all-yes || true
	fi

	if use kernel && [[ "${MERGE_TYPE}" != "binpkg" ]]; then
		ewarn "Re-emerge app-laptop/zenbook-scripts after each kernel upgrade"
		ewarn "(oot hid-asus.ko is per-KV_FULL)."
		ewarn "Boot sideload: rc-update add zenbook-kb-hid-asus boot"
		ewarn "               rc-service zenbook-kb-hid-asus start"
		ewarn "Hotkeys:       rc-update add zenbook-kb-hotkeys default"
		ewarn "Set fn_row_policy=7 in /etc/conf.d/zenbook-kb-hid-asus for docked UX8406."
	fi
}
