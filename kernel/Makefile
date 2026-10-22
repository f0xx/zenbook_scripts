.PHONY: all build clean patches build-7.0.12 build-7.1.3 build-7.1.5 build-7.2.0 \
	install modules_install install-7.0.12 install-7.1.3 install-7.1.5 install-7.2.0 \
	modules_install-7.0.12 modules_install-7.1.3 modules_install-7.1.5 modules_install-7.2.0

KERNEL_DIR := $(dir $(lastword $(MAKEFILE_LIST)))
OOT        := $(KERNEL_DIR)hid-asus-oot
KDIR       ?= /lib/modules/$(shell uname -r)/build
KDIR_7012  ?= /usr/src/linux-7.0.12-gentoo-r1
KDIR_713   ?= /usr/src/linux-7.1.3-gentoo
KDIR_715   ?= /usr/src/linux-7.1.5-gentoo
KDIR_720   ?= /usr/src/linux-7.2.0-gentoo

all: build

build:
	$(MAKE) -C "$(OOT)" KDIR="$(KDIR)"

build-current: build

build-7.0.12:
	$(MAKE) -C "$(OOT)" KDIR="$(KDIR_7012)"

build-7.1.3:
	$(MAKE) -C "$(OOT)" KDIR="$(KDIR_713)"

build-7.1.5:
	$(MAKE) -C "$(OOT)" KDIR="$(KDIR_715)"

build-7.2.0:
	$(MAKE) -C "$(OOT)" KDIR="$(KDIR_720)"

# Root required. modules_install → kbuild (…/extra/); install also copies to
# /usr/lib/modules/zenbook-hid-asus/<kver>/ for boot sideload.
modules_install:
	$(MAKE) -C "$(OOT)" KDIR="$(KDIR)" modules_install

install:
	$(MAKE) -C "$(OOT)" KDIR="$(KDIR)" install

modules_install-7.0.12:
	$(MAKE) -C "$(OOT)" KDIR="$(KDIR_7012)" modules_install

install-7.0.12:
	$(MAKE) -C "$(OOT)" KDIR="$(KDIR_7012)" install

modules_install-7.1.3:
	$(MAKE) -C "$(OOT)" KDIR="$(KDIR_713)" modules_install

install-7.1.3:
	$(MAKE) -C "$(OOT)" KDIR="$(KDIR_713)" install

modules_install-7.1.5:
	$(MAKE) -C "$(OOT)" KDIR="$(KDIR_715)" modules_install

install-7.1.5:
	$(MAKE) -C "$(OOT)" KDIR="$(KDIR_715)" install

modules_install-7.2.0:
	$(MAKE) -C "$(OOT)" KDIR="$(KDIR_720)" modules_install

install-7.2.0:
	$(MAKE) -C "$(OOT)" KDIR="$(KDIR_720)" install

clean:
	$(MAKE) -C "$(OOT)" clean

patches: patches-7.0.12 patches-7.1.3 patches-7.1.5 patches-7.2.0

patches-7.0.12:
	@mkdir -p patches/linux-7.0.12-gentoo-r1
	$(MAKE) -C "$(OOT)" prepare KDIR="$(KDIR_7012)"
	diff -u "$(KDIR_7012)/drivers/hid/hid-asus.c" \
		build/linux-7.0.12-gentoo-r1/hid-asus.c \
		> patches/linux-7.0.12-gentoo-r1/ux8406-hid-asus.patch || true

patches-7.1.3:
	@mkdir -p patches/linux-7.1.3-gentoo
	$(MAKE) -C "$(OOT)" prepare KDIR="$(KDIR_713)"
	diff -u "$(KDIR_713)/drivers/hid/hid-asus.c" \
		build/linux-7.1.3-gentoo/hid-asus.c \
		> patches/linux-7.1.3-gentoo/ux8406-hid-asus.patch || true

patches-7.1.5:
	@mkdir -p patches/linux-7.1.5-gentoo
	$(MAKE) -C "$(OOT)" prepare KDIR="$(KDIR_715)"
	diff -u "$(KDIR_715)/drivers/hid/hid-asus.c" \
		build/linux-7.1.5-gentoo/hid-asus.c \
		> patches/linux-7.1.5-gentoo/ux8406-hid-asus.patch || true

patches-7.2.0:
	@mkdir -p patches/linux-7.2.0-gentoo
	$(MAKE) -C "$(OOT)" prepare KDIR="$(KDIR_720)"
	diff -u "$(KDIR_720)/drivers/hid/hid-asus.c" \
		build/linux-7.2.0-gentoo/hid-asus.c \
		> patches/linux-7.2.0-gentoo/ux8406-hid-asus.patch || true
