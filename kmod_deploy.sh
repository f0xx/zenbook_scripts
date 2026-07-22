#!/bin/bash
ROW_POLICY=${ROW_POLICY:-7}
KVER="$(uname -r)"
make -C kernel || exit
sudo ./kernel/scripts/unload-hid-asus.sh && sudo rmmod hid_asus
sudo insmod "kernel/build/linux-${KVER}/hid-asus.ko" \
	fn_row_policy="${ROW_POLICY}" fn_lock_default=0 fn_lock_allow_toggle=1 || exit
sudo ./kernel/scripts/rebind-hid-asus.sh
sudo rc-service -q zenbook-kb-hotkeys status >/dev/null 2>&1 && \
	sudo rc-service zenbook-kb-hotkeys stop || true
cat /sys/module/hid_asus/parameters/fn_row_policy   # must be ROW_POLICY value
cat /sys/module/hid_asus/parameters/fn_lock_allow_toggle  # must be Y

echo "run: cd repo && sudo PYTHONPATH=. python3 -m zenbook_kb.sniff 15"
echo "fn_row_policy=$(cat /sys/module/hid_asus/parameters/fn_row_policy) (expected=${ROW_POLICY})"
echo "fn_lock_allow_toggle=$(cat /sys/module/hid_asus/parameters/fn_lock_allow_toggle) (expected=Y — Fn+Esc Mode A/B)"
