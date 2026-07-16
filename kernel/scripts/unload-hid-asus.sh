#!/bin/bash
# Safely unload sideloaded hid-asus.ko (unbind HID devices from asus before rmmod).
set -euo pipefail

if [[ ! -d /sys/module/hid_asus ]]; then
	echo "hid_asus is not loaded"
	exit 0
fi

echo "Unbinding UX8406 HID interfaces from asus…"
shopt -s nullglob

is_touchpad_node() {
	local node="$1"
	local name rdesc
	name="$(basename "$node")"
	[[ "$name" == *004C* ]] && return 0
	[[ -f "$node/report_descriptor" ]] || return 1
	rdesc="$(wc -c <"$node/report_descriptor")"
	[[ "$rdesc" -ge 200 ]]
}

for node in /sys/bus/hid/devices/*0B05*1B2C*; do
	name="$(basename "$node")"
	drv="$(basename "$(readlink -f "$node/driver" 2>/dev/null)" 2>/dev/null || echo none)"
	[[ "$drv" == "asus" ]] || continue
	echo "$name" >"/sys/bus/hid/drivers/asus/unbind" 2>/dev/null || true
	if [[ ! -e "$node/driver" ]]; then
		if is_touchpad_node "$node"; then
			echo "$name" >"/sys/bus/hid/drivers/hid-multitouch/bind" 2>/dev/null \
				|| echo "$name" >"/sys/bus/hid/drivers/hid-generic/bind" 2>/dev/null \
				|| true
		elif [[ -w /sys/bus/hid/drivers/hid-generic/bind ]]; then
			echo "$name" >"/sys/bus/hid/drivers/hid-generic/bind" 2>/dev/null || true
		fi
	fi
done
shopt -u nullglob

sleep 0.5
if modprobe -r hid_asus 2>/dev/null; then
	echo "hid_asus unloaded."
else
	rmmod hid_asus
	echo "hid_asus unloaded (rmmod)."
fi
echo "Restore stock: sudo modprobe hid_asus"
echo "Sideload again: sudo insmod build/linux-\$(uname -r)/hid-asus.ko && sudo ./scripts/rebind-hid-asus.sh"
