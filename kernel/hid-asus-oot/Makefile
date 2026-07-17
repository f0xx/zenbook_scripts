# Out-of-tree hid-asus with UX8406 Zenbook Duo patches.
#
# Usage:
#   make KDIR=/usr/src/linux-7.0.12-gentoo-r1
#   make KDIR=/usr/src/linux-7.1.3-gentoo
#   sudo make install              # zenbook sideload path + kbuild modules_install
#   sudo make modules_install      # kbuild only (…/lib/modules/<kver>/extra/)

KDIR ?= /lib/modules/$(shell uname -r)/build
ROOT := ..
PORT := $(ROOT)/scripts/port-ux8406.py
# Resolve /lib/modules/$(uname -r)/build → /usr/src/linux-<ver> for artifact paths.
KVER := $(notdir $(realpath $(KDIR)))
# Running/module version (7.0.12-gentoo-r1), not the linux- src dirname.
# Prefer the built tree's kernel.release (avoid recursive $(MAKE) — inherits -n).
KERNELRELEASE ?= $(shell cat "$(KDIR)/include/config/kernel.release" 2>/dev/null)
ifeq ($(KERNELRELEASE),)
KERNELRELEASE := $(patsubst linux-%,%,$(KVER))
endif
# kbuild M= paths cannot contain spaces; default under /tmp, per-UID so a
# prior root build does not leave a dir the portage user cannot write.
# Ebuild/emerge should pass BUILDDIR=$(T)/hid-asus-oot.
BUILDDIR ?= /tmp/zenbook-hid-asus-$(KVER)-$(shell id -u)
ARTIFACTS := $(ROOT)/build/$(KVER)
# Boot/sideload path (see switch-hid-asus.sh / OpenRC boot hook).
ZENBOOK_KO_ROOT ?= /usr/lib/modules/zenbook-hid-asus
DESTDIR ?=

.PHONY: all prepare clean modules install modules_install

all: modules

prepare:
	@test -d "$(KDIR)" || (echo "KDIR $(KDIR) not found" >&2; exit 1)
	@mkdir -p "$(BUILDDIR)" "$(ARTIFACTS)"
	cp "$(KDIR)/drivers/hid/hid-asus.c" "$(ARTIFACTS)/hid-asus.c.orig"
	"$(PORT)" "$(KDIR)" "$(BUILDDIR)/hid-asus.c"
	cp ux8406-ids.h "$(BUILDDIR)/"
	cp Makefile.module "$(BUILDDIR)/Makefile"
	cp "$(BUILDDIR)/hid-asus.c" "$(ARTIFACTS)/hid-asus.c"

modules: prepare
	# Portage exports ARCH=amd64; kbuild wants ARCH=x86 on that host.
	$(MAKE) -C "$(KDIR)" M="$(BUILDDIR)" ARCH="$(or $(KERNEL_ARCH),$(shell uname -m | sed -e s/x86_64/x86/ -e s/i.86/x86/))" modules
	@cp -f "$(BUILDDIR)/hid-asus.ko" "$(ARTIFACTS)/" 2>/dev/null || \
	 cp -f "$(BUILDDIR)/hid-asus.ko.xz" "$(ARTIFACTS)/" 2>/dev/null || true

clean:
	rm -rf "$(ROOT)/build" /tmp/zenbook-hid-asus-*

# Standard kbuild external-module install → $(DESTDIR)/lib/modules/$(KERNELRELEASE)/extra|updates/
modules_install: modules
	$(MAKE) -C "$(KDIR)" M="$(BUILDDIR)" modules_install

# Also install the .ko where boot sideload / switch-hid-asus expect it.
install: modules_install
	install -d "$(DESTDIR)$(ZENBOOK_KO_ROOT)/$(KERNELRELEASE)"
	install -m 644 "$(ARTIFACTS)/hid-asus.ko" \
		"$(DESTDIR)$(ZENBOOK_KO_ROOT)/$(KERNELRELEASE)/hid-asus.ko"
	@echo "Installed $(DESTDIR)$(ZENBOOK_KO_ROOT)/$(KERNELRELEASE)/hid-asus.ko"
