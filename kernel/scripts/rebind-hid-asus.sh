#!/bin/bash
# Re-bind UX8406 detachable keyboard (0b05:1b2c) to the sideloaded hid-asus module.
# Run after: sudo insmod kernel/build/linux-$(uname -r)/hid-asus.ko
#
# Strategy (matches the stable sideload layout before touchpad regressions):
#   - touchpad (USB if5, large rdesc) → hid-multitouch, never asus
#   - keyboard if0–if3 + vendor if4 → asus
set -euo pipefail

if [[ ! -d /sys/module/hid_asus ]]; then
	echo "hid_asus module is not loaded (/sys/module/hid_asus missing)" >&2
	echo "Load first: sudo insmod kernel/build/linux-\$(uname -r)/hid-asus.ko" >&2
	exit 1
fi

if ! lsusb -d 0b05:1b2c >/dev/null 2>&1; then
	echo "Keyboard USB device 0b05:1b2c not found" >&2
	exit 1
fi

USB_PORT=""
for p in /sys/bus/usb/devices/*-*; do
	[[ -f "$p/idVendor" && -f "$p/idProduct" ]] || continue
	if [[ "$(cat "$p/idVendor")" == "0b05" && "$(cat "$p/idProduct")" == "1b2c" ]]; then
		USB_PORT="$(basename "$p")"
		break
	fi
done

echo "USB port: ${USB_PORT:-unknown}"

_usb_if_num() {
	local node="$1" path
	path="$(readlink -f "$node" 2>/dev/null || true)"
	[[ "$path" =~ :1\.([0-9]+)/ ]] || return 1
	echo "${BASH_REMATCH[1]}"
}

is_touchpad_node() {
	local node="$1" name ifnum rdesc
	name="$(basename "$node")"
	[[ "$name" == *004C* || "$name" == *0006* ]] && return 0
	ifnum="$(_usb_if_num "$node" 2>/dev/null || true)"
	[[ "$ifnum" == "5" ]] && return 0
	[[ -f "$node/report_descriptor" ]] || return 1
	rdesc="$(wc -c <"$node/report_descriptor")"
	[[ "$rdesc" -ge 200 ]]
}

is_vendor_if4_node() {
	local node="$1" name ifnum rdesc
	name="$(basename "$node")"
	[[ "$name" == *004B* || "$name" == *004D* || "$name" == *004E* || "$name" == *000B* ]] && return 0
	ifnum="$(_usb_if_num "$node" 2>/dev/null || true)"
	[[ "$ifnum" == "4" ]] && return 0
	[[ -f "$node/report_descriptor" ]] || return 1
	rdesc="$(wc -c <"$node/report_descriptor")"
	[[ "$rdesc" -ge 90 && "$rdesc" -le 120 ]]
}

rebind_hid() {
	local id="$1"
	local drv path
	path="/sys/bus/hid/devices/$id"
	[[ -e "$path" ]] || return 0
	drv="$(basename "$(readlink -f "$path/driver" 2>/dev/null)" 2>/dev/null || echo none)"
	if [[ "$drv" == "asus" ]]; then
		echo "already asus: $id"
		return 0
	fi
	if [[ "$drv" != "none" && -n "$drv" ]]; then
		echo "$id" >"/sys/bus/hid/drivers/$drv/unbind"
	fi
	echo "$id" >"/sys/bus/hid/drivers/asus/bind"
	echo "bound $id → asus"
}

bind_hid_driver() {
	local id="$1"
	local target="$2"
	local drv path
	path="/sys/bus/hid/devices/$id"
	[[ -e "$path" ]] || return 1
	drv="$(basename "$(readlink -f "$path/driver" 2>/dev/null)" 2>/dev/null || echo none)"
	if [[ "$drv" == "$target" ]]; then
		echo "already $target: $id"
		return 0
	fi
	if [[ "$drv" != "none" && -n "$drv" ]]; then
		echo "$id" >"/sys/bus/hid/drivers/$drv/unbind" 2>/dev/null || true
	fi
	echo "$id" >"/sys/bus/hid/drivers/$target/bind"
	echo "bound $id → $target"
}

restore_touchpad() {
	local node name
	shopt -s nullglob
	for node in /sys/bus/hid/devices/*0B05*1B2C*; do
		[[ -e "$node" ]] || continue
		is_touchpad_node "$node" || continue
		name="$(basename "$node")"
		for drv in hid-multitouch hid-generic; do
			if bind_hid_driver "$name" "$drv" 2>/dev/null; then
				break
			fi
		done
	done
	shopt -u nullglob
}

# insmod grabs every 0b05:1b2c HID intf — restore touchpad before anything else.
restore_touchpad

shopt -s nullglob
have_vendor_if4=false
for node in /sys/bus/hid/devices/*0B05*1B2C*; do
	[[ -e "$node" ]] || continue
	if is_touchpad_node "$node"; then
		continue
	fi
	if is_vendor_if4_node "$node"; then
		have_vendor_if4=true
	fi
	rebind_hid "$(basename "$node")"
done

# Interface 4 (vendor / ep 0x85) — reprobe only if the node is missing.
if [[ "$have_vendor_if4" == false && -n "${USB_PORT:-}" && -d "/sys/bus/usb/devices/${USB_PORT}:1.4" ]]; then
	echo "re-probing USB interface 4 (${USB_PORT}:1.4)…"
	echo "${USB_PORT}:1.4" >"/sys/bus/usb/drivers/usbhid/unbind" 2>/dev/null || true
	sleep 0.5
	echo "${USB_PORT}:1.4" >"/sys/bus/usb/drivers/usbhid/bind"
	sleep 0.5
	for node in /sys/bus/hid/devices/*0B05*1B2C*; do
		[[ -e "$node" ]] || continue
		is_touchpad_node "$node" && continue
		is_vendor_if4_node "$node" && have_vendor_if4=true
		rebind_hid "$(basename "$node")"
	done
fi

restore_touchpad
shopt -u nullglob

echo
echo "HID nodes:"
for node in /sys/bus/hid/devices/*0B05*1B2C*; do
	[[ -e "$node" ]] || continue
	name="$(basename "$node")"
	drv="$(basename "$(readlink -f "$node/driver" 2>/dev/null)" 2>/dev/null || echo none)"
	rdesc="$(wc -c <"$node/report_descriptor" 2>/dev/null || echo 0)"
	ifnum="$(_usb_if_num "$node" 2>/dev/null || echo "?")"
	kind="other"
	is_touchpad_node "$node" && kind="touchpad"
	is_vendor_if4_node "$node" && kind="vendor-if4"
	[[ "$ifnum" =~ ^[0-3]$ ]] && kind="keyboard-if${ifnum}"
	echo "  $name if=${ifnum} driver=$drv rdesc=${rdesc}B ($kind)"
done

echo
echo "Expect interface-4 node on asus with dmesg:"
echo "  Fixing up ZENBOOK DUO keyb report descriptor"
echo "  Injecting virtual Zenbook Duo keyboard usage page"
echo
echo "Do not start zenbook-kb-hotkeys until usb_poll is off or hid-asus owns if4"
echo "(service pyusb claim on if4 bricks the docked keyboard)."
