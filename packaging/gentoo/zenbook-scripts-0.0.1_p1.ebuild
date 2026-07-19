# Copyright 1999-2026 Gentoo Authors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

inherit linux-info toolchain-funcs

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

IUSE="+fan_control +hotkeys +kernel qt6 screenpad +zenbook_ux8406"
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

ZENBOOK_SHARE=/usr/share/zenbook-scripts
ZENBOOK_LIBEXEC=/usr/libexec
ZENBOOK_KO_ROOT=/usr/lib/modules/zenbook-hid-asus

# Upstream trees default to /usr/local (configure.py). Distro packages use /usr.
zenbook_rewrite_usr_prefix() {
	local dir f

	for dir in \
		"${ED}${ZENBOOK_SHARE}" \
		"${ED}${ZENBOOK_LIBEXEC}" \
		"${ED}/usr/bin" \
		"${ED}/etc" \
		"${ED}/usr/lib/systemd"; do
		[[ -d ${dir} ]] || continue
		while IFS= read -r -d '' f; do
			grep -q '/usr/local/' "${f}" 2>/dev/null || continue
			sed -e 's|/usr/local/|/usr/|g' -i -- "${f}" || die "sed ${f}"
		done < <(find "${dir}" -type f -print0)
	done
}

# Prefer linux-info KV_OUT_DIR (modules …/build if present, else /usr/src/linux).
# Source-based gentoo-sources often have no /lib/modules/<KV>/build until
# modules_install — dist-kernel always has that symlink.
zenbook_kernel_kdir() {
	local kdir="${KERNEL_SRC_PATH:-${KV_OUT_DIR}}"

	if [[ -z ${kdir} || ! -d ${kdir} ]]; then
		kdir="${ESYSROOT}/lib/modules/${KV_FULL}/build"
	fi
	if [[ ! -d ${kdir} && -d ${KERNEL_DIR} ]]; then
		kdir="${KERNEL_DIR}"
	fi
	[[ -d ${kdir} ]] || die \
		"No kernel build tree for KDIR=${kdir:-unset} (KV_FULL=${KV_FULL}).\n" \
		"  eselect kernel set <N> to your running kernel, or ensure\n" \
		"  ${ESYSROOT}/lib/modules/\$(uname -r)/build exists (make modules_install)."
	echo "${kdir}"
}

zenbook_kernel_release() {
	local kdir release

	kdir=$(zenbook_kernel_kdir)
	if [[ -s ${kdir}/include/config/kernel.release ]]; then
		echo "$(<"${kdir}/include/config/kernel.release")"
		return
	fi
	# Fallback: dirname linux-7.0.12-gentoo-r1 → 7.0.12-gentoo-r1
	release=$(basename "$(realpath -e "${kdir}" 2>/dev/null || echo "${kdir}")")
	echo "${release#linux-}"
}

pkg_setup() {
	if use kernel; then
		linux-info_pkg_setup
		# Resolve KDIR early so emerge fails with a clear message.
		zenbook_kernel_kdir >/dev/null
		if [[ ${KV_FULL} != "$(uname -r)" ]]; then
			ewarn "Building oot hid-asus for ${KV_FULL}, running kernel is $(uname -r)."
			ewarn "For a loadable module now: eselect kernel set to match uname -r, then re-emerge."
		fi
	fi
}

src_compile() {
	if use kernel; then
		local kdir

		kdir=$(zenbook_kernel_kdir)
		einfo "Building hid-asus against KDIR=${kdir}"
		# Portage ARCH=amd64 breaks kbuild (expects ARCH=x86).
		local -x ARCH
		ARCH="$(tc-arch-kernel)"
		# BUILDDIR under ${T}: /tmp/zenbook-hid-asus-* may be owned by a
		# prior interactive build (foxx/root) and is unwritable to portage.
		emake -C "${S}/kernel" build-current \
			KDIR="${kdir}" \
			BUILDDIR="${T}/hid-asus-oot"
	fi
}

src_install() {
	# Python + shell support tree
	insinto "${ZENBOOK_SHARE}"
	doins -r zenbook_kb brightness.py lib
	doins zenbook-hotkeys.conf.example zenbook-duo.conf.example
	if use fan_control; then
		doins fan-control.json.example
		insinto /etc/zenbook-scripts
		newins fan-control.json.example fan-control.json.example
	fi

	if use zenbook_ux8406; then
		insinto "${ZENBOOK_SHARE}/conf.d"
		doins conf.d/00-default.evdev.conf
		for f in conf.d/UX8406*.evdev.conf conf.d/UX8406*.usb.conf; do
			[[ -f "${S}/${f}" ]] || continue
			doins "${f}"
		done
	fi

	# User-facing CLIs
	dobin configure.py configure.sh bin/kb-brightness bin/kb-platform-profile bin/platform-fan bin/platform-probe
	dobin bin/kb-fan
	if use fan_control; then
		dobin bin/platform-fan-control bin/kb-fan-control
	fi
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
	if use fan_control; then
		newbin contrib/openrc/zenbook-fan-control-hook.sh zenbook-fan-control-hook
	fi
	if use qt6; then
		dobin configure_gui.py
		dobin bin/platform-tray
	fi

	if use hotkeys; then
		insinto "${ZENBOOK_LIBEXEC}"
		newins contrib/udev/zenbook-kb-hotkeys-udev zenbook-kb-hotkeys-udev
		newins contrib/acpi/zenbook-kbd-sleep.sh zenbook-kbd-sleep.sh
		fperms 0755 \
			"${ZENBOOK_LIBEXEC}/zenbook-kb-hotkeys-udev" \
			"${ZENBOOK_LIBEXEC}/zenbook-kbd-sleep.sh"

		insinto /etc/udev/rules.d
		doins contrib/udev/99-zenbook-kb-hotkeys.rules

		insinto /etc/acpi/events
		doins contrib/acpi/events/zenbook-kbd-sleep

		insinto /usr/lib/systemd/system-sleep
		newins contrib/systemd/zenbook-kb-brightness-sleep zenbook-kb-brightness
		fperms 0755 /usr/lib/systemd/system-sleep/zenbook-kb-brightness

		newinitd contrib/openrc/zenbook-kb-hotkeys zenbook-kb-hotkeys
		newinitd contrib/openrc/zenbook-kb-lid zenbook-kb-lid

		insinto /etc/modprobe.d
		doins contrib/modprobe/zenbook-hid-asus.conf
	fi

	if use fan_control; then
		newinitd contrib/openrc/zenbook-platform-fan-control zenbook-platform-fan-control
		newconfd contrib/openrc/conf.d/zenbook-platform-fan-control zenbook-platform-fan-control
		dosym zenbook-platform-fan-control /etc/init.d/zenbook-kb-fan-control
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
			"${ZENBOOK_LIBEXEC}/zenbook-hid-asus-switch" \
			"${ZENBOOK_LIBEXEC}/zenbook-hid-asus-rebind" \
			"${ZENBOOK_LIBEXEC}/zenbook-hid-asus-boot.sh"

		newinitd contrib/openrc/zenbook-kb-hid-asus zenbook-kb-hid-asus
		newconfd contrib/openrc/conf.d/zenbook-kb-hid-asus zenbook-kb-hid-asus

		local ko kver
		# OOT Makefile writes to kernel/build/<realpath-basename>/hid-asus.ko
		ko="$(find "${S}/kernel/build" -name 'hid-asus.ko' -print -quit)"
		[[ -n ${ko} && -f ${ko} ]] || die "missing built module under ${S}/kernel/build/"
		kver="$(zenbook_kernel_release)"
		insinto "${ZENBOOK_KO_ROOT}/${kver}"
		doins "${ko}"
	fi

	local doc
	for doc in LICENSE DEPLOY.md README.ux8406.md README.ux5400.md \
		kernel/README.md packaging/README.md PLANNED.md ROADMAP.md README.md; do
		[[ -f "${S}/${doc}" ]] || continue
		dodoc "${doc}"
	done

	zenbook_rewrite_usr_prefix
}

pkg_postinst() {
	# Do not run configure.py here — it installs into /usr/local and fights
	# the Gentoo /usr layout.

	elog "Gentoo layout: /usr/bin, /usr/libexec, /usr/share/zenbook-scripts"
	elog "(configure.py from a git tree still uses /usr/local by design)."

	if use fan_control; then
		elog "Fan-control (USE=fan_control):"
		elog "  sudo cp /etc/zenbook-scripts/fan-control.json.example \\"
		elog "          /etc/zenbook-scripts/fan-control.json"
		elog "  sudo rc-update add zenbook-platform-fan-control default"
		elog "  sudo rc-service zenbook-platform-fan-control start"
		elog "  platform-probe && platform-fan-control check"
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
