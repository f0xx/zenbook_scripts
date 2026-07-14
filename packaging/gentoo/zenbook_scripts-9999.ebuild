# Copyright 1999-2026 Gentoo Authors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

inherit git-r3 linux-info openrc

DESCRIPTION="ASUS Zenbook Duo UX8406 detachable keyboard brightness, Fn+ hotkeys, and oot hid-asus"
HOMEPAGE="https://github.com/f0xx/zenbook_scripts"
EGIT_REPO_URI="https://github.com/f0xx/zenbook_scripts.git"

LICENSE="GPL-2+"
SLOT="0"
KEYWORDS=""

IUSE="hotkeys kernel qt6 zenbook_ux8406"
REQUIRED_USE="kernel? ( zenbook_ux8406 )"

RDEPEND="
	>=dev-lang/python-3.10
	dev-python/pyusb
	hotkeys? (
		sys-auth/udev
		acpid
		virtual/elogind
	)
	qt6? ( dev-python/pyside6 )
	kernel? (
		virtual/dist-kernel
		>=sys-devel/make-4
	)
"
DEPEND="${RDEPEND}"

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
	dobin configure.py configure.sh bin/kb-brightness
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

	dodoc README.md DEPLOY.md LICENSE kernel/README.md packaging/README.md PLANNED.md
}

pkg_postinst() {
	openrc_pkg_postinst

	if use hotkeys; then
		"${ROOT}${EPREFIX}/usr/bin/python3" \
			"${ROOT}${EPREFIX}/usr/local/bin/configure.py" --defaults --all-yes || true
	fi

	if use kernel && [[ "${MERGE_TYPE}" != "binpkg" ]]; then
		ewarn "Re-emerge zenbook_scripts after each kernel upgrade (oot hid-asus.ko is per-KV_FULL)."
		ewarn "Boot sideload: rc-service zenbook-kb-hid-asus start (enabled in boot runlevel)."
	fi
}

pkg_postrm() {
	openrc_pkg_postrm
}

pkg_prerm() {
	openrc_pkg_prerm
}
