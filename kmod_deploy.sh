#!/bin/bash
ROW_POLICY=${ROW_POLICY:-7}
KVER="$(uname -r)"
make -C kernel || exit
sudo ./kernel/scripts/unload-hid-asus.sh && sudo rmmod hid_asus
sudo insmod "kernel/build/linux-${KVER}/hid-asus.ko" \
	fn_row_policy="${ROW_POLICY}" fn_lock_default=0 fn_lock_allow_toggle=0 || exit
sudo ./kernel/scripts/rebind-hid-asus.sh
sudo rc-service zenbook-kb-hotkeys stop
cat /sys/module/hid_asus/parameters/fn_row_policy   # must be ROW_POLICY value

echo "run: cd repo && sudo PYTHONPATH=. python3 -m zenbook_kb.sniff 15"
echo "fn_row_policy=$(cat /sys/module/hid_asus/parameters/fn_row_policy) (expected=${ROW_POLICY})"
