#!/bin/sh
# Install zenbook_scripts into a Debian package root (DESTDIR layout).
# configure.py has --prefix but no DESTDIR and uses sudo for /etc paths;
# packaging must not run configure.py during build.
set -eu

PKGROOT="${1:?usage: install.sh <debian/zenbook-scripts>}"
SCRIPT_DIR="$(CDPATH= cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(CDPATH= cd "${SCRIPT_DIR}/../.." && pwd)"

PREFIX="${PKGROOT}/usr"
SHARE="${PREFIX}/share/zenbook-scripts"
LIBEXEC="${PREFIX}/libexec"
BINDIR="${PREFIX}/bin"

install -d "${SHARE}/lib" "${SHARE}/zenbook_kb" "${SHARE}/conf.d" \
	"${LIBEXEC}" "${BINDIR}" \
	"${PKGROOT}/etc/zenbook-scripts" \
	"${PKGROOT}/etc/udev/rules.d" \
	"${PKGROOT}/etc/acpi/events" \
	"${PKGROOT}/etc/modprobe.d" \
	"${PKGROOT}/etc/systemd/system" \
	"${PKGROOT}/usr/lib/systemd/system-sleep" \
	"${PKGROOT}/usr/share/doc/zenbook-scripts"

# Share tree (Python + shell support)
cp -a "${REPO_ROOT}/zenbook_kb" "${SHARE}/"
cp -a "${REPO_ROOT}/lib/." "${SHARE}/lib/"
cp -a "${REPO_ROOT}/conf.d/." "${SHARE}/conf.d/"
cp "${REPO_ROOT}/brightness.py" "${SHARE}/"
for f in zenbook-hotkeys.conf.example zenbook-duo.conf.example \
	touchpad.json.example fan-control.json.example; do
	[ -f "${REPO_ROOT}/${f}" ] || continue
	cp "${REPO_ROOT}/${f}" "${SHARE}/"
	cp "${REPO_ROOT}/${f}" "${PKGROOT}/etc/zenbook-scripts/" 2>/dev/null || true
done

# User-facing CLIs
for bin in configure.py configure.sh configure_gui.py; do
	[ -f "${REPO_ROOT}/${bin}" ] || continue
	install -m 755 "${REPO_ROOT}/${bin}" "${BINDIR}/"
done
for bin in "${REPO_ROOT}/bin/"*; do
	[ -f "${bin}" ] || continue
	install -m 755 "${bin}" "${BINDIR}/$(basename "${bin}")"
done

# libexec helpers
for helper in \
	contrib/udev/zenbook-kb-hotkeys-udev \
	contrib/udev/zenbook-duo-dock-udev \
	contrib/acpi/zenbook-kbd-sleep.sh \
	contrib/openrc/zenbook-fan-control-hook.sh \
	contrib/openrc/zenbook-hid-asus-boot.sh \
	contrib/openrc/zenbook-platform-session-hook.sh \
	kernel/scripts/switch-hid-asus.sh \
	kernel/scripts/rebind-hid-asus.sh; do
	src="${REPO_ROOT}/${helper}"
	[ -f "${src}" ] || continue
	dest_name="$(basename "${helper}")"
	case "${dest_name}" in
	zenbook-fan-control-hook.sh) dest_name=zenbook-fan-control-hook ;;
	zenbook-hid-asus-boot.sh) dest_name=zenbook-hid-asus-boot.sh ;;
	zenbook-platform-session-hook.sh) dest_name=zenbook-platform-session-hook ;;
	switch-hid-asus.sh) dest_name=zenbook-hid-asus-switch ;;
	rebind-hid-asus.sh) dest_name=zenbook-hid-asus-rebind ;;
	esac
	install -m 755 "${src}" "${LIBEXEC}/${dest_name}"
done

# udev rules (rewrite libexec paths to packaged /usr/libexec)
for rules in \
	contrib/udev/99-zenbook-kb-hotkeys.rules \
	contrib/udev/99-zenbook-duo-dock.rules \
	contrib/udev/99-zenbook-bt-fn-row.rules \
	contrib/udev/99-zenbook-screenpad.rules; do
	src="${REPO_ROOT}/${rules}"
	[ -f "${src}" ] || continue
	sed -e 's|/usr/local/libexec/|/usr/libexec/|g' \
		-e 's|/usr/local/bin/|/usr/bin/|g' \
		"${src}" > "${PKGROOT}/etc/udev/rules.d/$(basename "${rules}")"
done

# ACPI / modprobe / systemd units
[ -f "${REPO_ROOT}/contrib/acpi/events/zenbook-kbd-sleep" ] && \
	install -m 644 "${REPO_ROOT}/contrib/acpi/events/zenbook-kbd-sleep" \
		"${PKGROOT}/etc/acpi/events/zenbook-kbd-sleep"
[ -f "${REPO_ROOT}/contrib/modprobe/zenbook-hid-asus.conf" ] && \
	install -m 644 "${REPO_ROOT}/contrib/modprobe/zenbook-hid-asus.conf" \
		"${PKGROOT}/etc/modprobe.d/zenbook-hid-asus.conf"
for unit in contrib/systemd/zenbook-kb-hotkeys.service \
	contrib/systemd/zenbook-screenpad.service \
	contrib/systemd/zenbook-screenpad-sync.service \
	contrib/systemd/zenbook-platform-touchpad.service; do
	[ -f "${REPO_ROOT}/${unit}" ] || continue
	install -m 644 "${REPO_ROOT}/${unit}" \
		"${PKGROOT}/etc/systemd/system/$(basename "${unit}")"
done
for hook in contrib/systemd/zenbook-kb-brightness-sleep \
	contrib/systemd/zenbook-platform-session; do
	[ -f "${REPO_ROOT}/${hook}" ] || continue
	dest_name="$(basename "${hook}")"
	case "${dest_name}" in
	zenbook-kb-brightness-sleep) dest_name=zenbook-kb-brightness ;;
	esac
	install -m 755 "${REPO_ROOT}/${hook}" \
		"${PKGROOT}/usr/lib/systemd/system-sleep/${dest_name}"
done

# Plasma session example + docs (KCM not built here)
if [ -f "${REPO_ROOT}/plasma/session.json.example" ]; then
	install -d "${SHARE}/plasma"
	install -m 644 "${REPO_ROOT}/plasma/session.json.example" "${SHARE}/plasma/"
fi
for doc in README.md README.plasma.md DEPLOY.md plasma/README.md \
	LICENSE kernel/README.md; do
	[ -f "${REPO_ROOT}/${doc}" ] || continue
	install -m 644 "${REPO_ROOT}/${doc}" "${PKGROOT}/usr/share/doc/zenbook-scripts/"
done

# OpenRC units ship as examples (Debian defaults to systemd)
install -d "${PKGROOT}/usr/share/doc/zenbook-scripts/examples/openrc"
for rc in contrib/openrc/zenbook-kb-hotkeys \
	contrib/openrc/zenbook-kb-lid \
	contrib/openrc/zenbook-kb-hid-asus \
	contrib/openrc/zenbook-platform-fan-control \
	contrib/openrc/zenbook-screenpad \
	contrib/openrc/zenbook-screenpad-sync \
	contrib/openrc/zenbook-bt-fn-row; do
	[ -f "${REPO_ROOT}/${rc}" ] || continue
	install -m 755 "${REPO_ROOT}/${rc}" \
		"${PKGROOT}/usr/share/doc/zenbook-scripts/examples/openrc/$(basename "${rc}")"
done
for conf in contrib/openrc/conf.d/*; do
	[ -f "${conf}" ] || continue
	install -m 644 "${conf}" \
		"${PKGROOT}/usr/share/doc/zenbook-scripts/examples/openrc/"
done

echo "Installed CLI tree under ${PREFIX}"
