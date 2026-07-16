.PHONY: all build clean patches build-7.0.12 build-7.1.3

KERNEL_DIR := $(dir $(lastword $(MAKEFILE_LIST)))
OOT        := $(KERNEL_DIR)hid-asus-oot
KDIR       ?= /lib/modules/$(shell uname -r)/build
KDIR_7012  ?= /usr/src/linux-7.0.12-gentoo-r1
KDIR_713   ?= /usr/src/linux-7.1.3-gentoo

all: build

build:
	$(MAKE) -C "$(OOT)" KDIR="$(KDIR)"

build-current: build

build-7.0.12:
	$(MAKE) -C "$(OOT)" KDIR="$(KDIR_7012)"

build-7.1.3:
	$(MAKE) -C "$(OOT)" KDIR="$(KDIR_713)"

clean:
	$(MAKE) -C "$(OOT)" clean

patches: patches-7.0.12 patches-7.1.3

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
