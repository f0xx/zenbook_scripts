# Out-of-tree hid-asus with UX8406 Zenbook Duo patches.
#
# Usage:
#   make KDIR=/usr/src/linux-7.0.12-gentoo-r1
#   make KDIR=/usr/src/linux-7.1.3-gentoo

KDIR ?= /lib/modules/$(shell uname -r)/build
ROOT := ..
PORT := $(ROOT)/scripts/port-ux8406.py
KVER := $(notdir $(KDIR))
# kbuild cannot use module paths containing spaces; build under /tmp.
BUILDDIR := /tmp/zenbook-hid-asus-$(KVER)
ARTIFACTS := $(ROOT)/build/$(KVER)

.PHONY: all prepare clean modules install

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
	$(MAKE) -C "$(KDIR)" M="$(BUILDDIR)" modules
	@cp -f "$(BUILDDIR)/hid-asus.ko" "$(ARTIFACTS)/" 2>/dev/null || \
	 cp -f "$(BUILDDIR)/hid-asus.ko.xz" "$(ARTIFACTS)/" 2>/dev/null || true

clean:
	rm -rf "$(ROOT)/build" /tmp/zenbook-hid-asus-*

install: modules
	$(MAKE) -C "$(KDIR)" M="$(BUILDDIR)" modules_install
