#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Apply UX8406 Zenbook Duo hid-asus changes onto a kernel-tree copy."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


QUIRK_BLOCK = """
#define QUIRK_ZENBOOK_DUO_KEYBOARD	BIT(16)

#define ZENBOOK_DUO_QUIRKS		(QUIRK_USE_KBD_BACKLIGHT | \\
					 QUIRK_HID_FN_LOCK | \\
					 QUIRK_ZENBOOK_DUO_KEYBOARD)
"""

HAS_VENDOR_FIELD = "\tbool has_vendor_up;\n"

DMI_AND_WMI_CHECK = """
static const struct dmi_system_id ux8406_hid_kbd_backlight_dmi[] = {
	{
		.matches = {
			DMI_MATCH(DMI_BOARD_NAME, "UX8406"),
		},
	},
	{
		.matches = {
			DMI_MATCH(DMI_BOARD_NAME, "UX8406MA"),
		},
	},
	{
		.matches = {
			DMI_MATCH(DMI_BOARD_NAME, "UX8406CA"),
		},
	},
	{ }
};

/* Prefer HID keyboard backlight on Zenbook Duo; WMI path is not used. */
static bool asus_kbd_wmi_led_control_present(struct hid_device *hdev)
{
	struct asus_drvdata *drvdata = hid_get_drvdata(hdev);
	u32 value;
	int ret;

	if (!IS_ENABLED(CONFIG_ASUS_WMI))
		return false;

	if ((drvdata->quirks & QUIRK_USE_KBD_BACKLIGHT) &&
	    dmi_check_system(ux8406_hid_kbd_backlight_dmi)) {
		hid_info(hdev, "using HID for asus::kbd_backlight\\n");
		return false;
	}

	ret = asus_wmi_evaluate_method(ASUS_WMI_METHODID_DSTS,
				      ASUS_WMI_DEVID_KBD_BACKLIGHT, 0, &value);
	hid_dbg(hdev, "WMI backlight check: rc %d value %x", ret, value);
	if (ret)
		return false;

	return !!(value & ASUS_WMI_DSTS_PRESENCE_BIT);
}

"""

FAKE_KBD_RDESC = """
/*
 * Zenbook Duo USB interface 4 is vendor-only; inject a minimal keyboard
 * collection so the HID core registers an input device for hotkey mapping.
 */
static const __u8 asus_fake_keyboard_rdesc[] = {
	0x05, 0x01,	/* Usage Page (Generic Desktop) */
	0x09, 0x06,	/* Usage (Keyboard) */
	0xa1, 0x01,	/* Collection (Application) */
	0x85, 0x01,	/*   Report ID (1) */
	0x75, 0x08,	/*   Report Size (8) */
	0x95, 0x01,	/*   Report Count (1) */
	0x81, 0x00,	/*   Input (Data,Array,Abs) */
	0xc0,		/* End Collection */
};

"""

ZENBOOK_QUIRK_FILTER = """
/* UX8406 exposes one PID on several USB interfaces; scope quirks narrowly. */
static void asus_filter_zenbook_usb_quirks(struct hid_device *hdev,
					   struct asus_drvdata *drvdata)
{
	unsigned int ifnum;

	if (!(drvdata->quirks & QUIRK_ZENBOOK_DUO_KEYBOARD) || !hid_is_usb(hdev))
		return;

	ifnum = to_usb_interface(hdev->dev.parent)->altsetting->desc.bInterfaceNumber;

	if (ifnum == 0) {
		/* Main typing keyboard — do not enable fn-lock/backlight quirks here. */
		drvdata->quirks &= ~(QUIRK_USE_KBD_BACKLIGHT | QUIRK_HID_FN_LOCK |
				     QUIRK_ZENBOOK_DUO_KEYBOARD);
		return;
	}

	if (ifnum != 4) {
		drvdata->quirks &= ~(QUIRK_ZENBOOK_DUO_KEYBOARD | QUIRK_HID_FN_LOCK |
				     QUIRK_USE_KBD_BACKLIGHT);
	}
}

"""


DEVICE_ENTRIES = """
\t{ HID_USB_DEVICE(USB_VENDOR_ID_ASUSTEK,
\t    USB_DEVICE_ID_ASUSTEK_ZENBOOK_DUO_KEYBOARD), ZENBOOK_DUO_QUIRKS },
\t{ HID_BLUETOOTH_DEVICE(USB_VENDOR_ID_ASUSTEK,
\t    BT_DEVICE_ID_ASUSTEK_ZENBOOK_DUO_KEYBOARD), ZENBOOK_DUO_QUIRKS },
"""


def insert_before(pattern: str, addition: str, text: str) -> str:
    m = re.search(pattern, text)
    if not m:
        raise SystemExit(f"pattern not found: {pattern!r}")
    pos = m.start()
    return text[:pos] + addition + text[pos:]


def insert_after(pattern: str, addition: str, text: str) -> str:
    m = re.search(pattern, text)
    if not m:
        raise SystemExit(f"pattern not found: {pattern!r}")
    pos = m.end()
    return text[:pos] + addition + text[pos:]


def replace_once(old: str, new: str, text: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"replace target not found ({label})")
    return text.replace(old, new, 1)


def port_hid_asus(src: Path, dst: Path) -> None:
    text = src.read_text()

    if "QUIRK_ZENBOOK_DUO_KEYBOARD" in text:
        dst.write_text(text)
        return

    text = insert_after(
        r'#include <linux/leds.h>\n',
        '#include <linux/platform_profile.h>\n#include "ux8406-ids.h"\n',
        text,
    )

    if "QUIRK_ROG_NKEY_ID1ID2_INIT" in text:
        text = insert_after(
            r"#define QUIRK_ROG_NKEY_ID1ID2_INIT\tBIT\(15\)\n",
            QUIRK_BLOCK,
            text,
        )
    else:
        text = insert_after(
            r"#define QUIRK_HID_FN_LOCK\t\tBIT\(14\)\n",
            QUIRK_BLOCK,
            text,
        )

    text = insert_after(
        r"\tconst struct asus_touchpad_info \*tp;\n",
        HAS_VENDOR_FIELD,
        text,
    )

    text = insert_after(
        r"static void asus_sync_fn_lock\(struct work_struct \*work\)\n\{\n"
        r"\tstruct asus_drvdata \*drvdata =\n"
        r"\tcontainer_of\(work, struct asus_drvdata, fn_lock_sync_work\);\n\n"
        r"\tasus_kbd_set_fn_lock\(drvdata->hdev, drvdata->fn_lock\);\n\}\n\n",
        DMI_AND_WMI_CHECK,
        text,
    )

    old_event = """\tif ((usage->hid & HID_USAGE_PAGE) == HID_UP_ASUSVENDOR &&
\t    (usage->hid & HID_USAGE) != 0x00 &&
\t    (usage->hid & HID_USAGE) != 0xff && !usage->type) {
\t\thid_warn(hdev, "Unmapped Asus vendor usagepage code 0x%02x\\n",
\t\t\t usage->hid & HID_USAGE);
\t}"""

    new_event = """\tif ((usage->hid & HID_USAGE_PAGE) == HID_UP_ASUSVENDOR &&
\t    (usage->hid & HID_USAGE) != 0x00 &&
\t    (usage->hid & HID_USAGE) != 0xff && !usage->type) {
\t\tswitch (usage->hid & HID_USAGE) {
\t\tcase 0x4e:
\t\t\tif (!value)
\t\t\t\tbreak;
\t\t\tif (drvdata->quirks & QUIRK_HID_FN_LOCK) {
\t\t\t\tdrvdata->fn_lock = !drvdata->fn_lock;
\t\t\t\tschedule_work(&drvdata->fn_lock_sync_work);
\t\t\t}
\t\t\treturn 1;
\t\tcase 0x9d:
\t\t\tif (!value)
\t\t\t\tbreak;
\t\t\treturn platform_profile_cycle();
\t\tdefault:
\t\t\thid_warn(hdev, "Unmapped Asus vendor usagepage code 0x%02x\\n",
\t\t\t\t usage->hid & HID_USAGE);
\t\t}
\t}"""

    text = replace_once(old_event, new_event, text, "asus_event vendor block")

    old_fnlock = """\tif (drvdata->quirks & QUIRK_HID_FN_LOCK) {
\t\tdrvdata->fn_lock = true;
\t\tINIT_WORK(&drvdata->fn_lock_sync_work, asus_sync_fn_lock);
\t\tasus_kbd_set_fn_lock(hdev, true);
\t}

\treturn 0;
}"""

    new_fnlock = """\tif (drvdata->quirks & QUIRK_HID_FN_LOCK) {
\t\tif (!(drvdata->quirks & QUIRK_ZENBOOK_DUO_KEYBOARD) ||
\t\t    drvdata->has_vendor_up) {
\t\t\tdrvdata->fn_lock = true;
\t\t\tINIT_WORK(&drvdata->fn_lock_sync_work, asus_sync_fn_lock);
\t\t\tasus_kbd_set_fn_lock(hdev, true);
\t\t}
\t}

\tif (drvdata->has_vendor_up &&
\t    (drvdata->quirks & QUIRK_USE_KBD_BACKLIGHT) &&
\t    !asus_kbd_wmi_led_control_present(hdev) &&
\t    asus_kbd_register_leds(hdev))
\t\thid_warn(hdev, "Failed to initialize backlight.\\n");

\treturn 0;
}"""

    text = replace_once(old_fnlock, new_fnlock, text, "asus_input_configured tail")

    text = replace_once(
        "\t\tset_bit(EV_REP, hi->input->evbit);\n\t\treturn 1;\n\t}\n\n\tif ((usage->hid & HID_USAGE_PAGE) == HID_UP_MSVENDOR)",
        "\t\tdrvdata->has_vendor_up = true;\n\t\tset_bit(EV_REP, hi->input->evbit);\n\t\treturn 1;\n\t}\n\n\tif ((usage->hid & HID_USAGE_PAGE) == HID_UP_MSVENDOR)",
        text,
        "has_vendor_up in input_mapping",
    )

    if "asus_report_id_init" in text:
        text = replace_once(
            "\tif (is_vendor && (drvdata->quirks & QUIRK_USE_KBD_BACKLIGHT) &&\n"
            "\t    (asus_has_report_id(hdev, FEATURE_KBD_REPORT_ID)) &&\n"
            "\t\t(asus_kbd_register_leds(hdev)))\n"
            "\t\thid_warn(hdev, \"Failed to initialize backlight.\\n\");",
            "\tif (is_vendor && (drvdata->quirks & QUIRK_USE_KBD_BACKLIGHT) &&\n"
            "\t    !(drvdata->quirks & QUIRK_ZENBOOK_DUO_KEYBOARD) &&\n"
            "\t    (asus_has_report_id(hdev, FEATURE_KBD_REPORT_ID)) &&\n"
            "\t\t(asus_kbd_register_leds(hdev)))\n"
            "\t\thid_warn(hdev, \"Failed to initialize backlight.\\n\");",
            text,
            "probe backlight zenbook skip (7.1.3)",
        )
    else:
        text = replace_once(
            "\tif (is_vendor && (drvdata->quirks & QUIRK_USE_KBD_BACKLIGHT) &&\n"
            "\t    asus_kbd_register_leds(hdev))\n"
            "\t\thid_warn(hdev, \"Failed to initialize backlight.\\n\");",
            "\tif (is_vendor && (drvdata->quirks & QUIRK_USE_KBD_BACKLIGHT) &&\n"
            "\t    !(drvdata->quirks & QUIRK_ZENBOOK_DUO_KEYBOARD) &&\n"
            "\t    asus_kbd_register_leds(hdev))\n"
            "\t\thid_warn(hdev, \"Failed to initialize backlight.\\n\");",
            text,
            "probe backlight zenbook skip (7.0.12)",
        )

    text = replace_once(
        "\tif (drvdata->quirks & QUIRK_ROG_NKEY_KEYBOARD)\n\t\treturn 0;",
        "\tif (drvdata->quirks & (QUIRK_ROG_NKEY_KEYBOARD | QUIRK_ZENBOOK_DUO_KEYBOARD))\n\t\treturn 0;",
        text,
        "probe early return",
    )

    text = insert_before(
        r"static int asus_probe\(struct hid_device \*hdev, const struct hid_device_id \*id\)\n",
        ZENBOOK_QUIRK_FILTER,
        text,
    )

    text = insert_before(
        r"static const __u8 asus_g752_fixed_rdesc\[\] = \{",
        FAKE_KBD_RDESC,
        text,
    )

    text = replace_once(
        "\tdrvdata->quirks = id->driver_data;\n\n\t/*\n\t * T90CHI's keyboard dock",
        "\tdrvdata->quirks = id->driver_data;\n\n\tasus_filter_zenbook_usb_quirks(hdev, drvdata);\n\n\t/*\n\t * T90CHI's keyboard dock",
        text,
        "asus_filter_zenbook_usb_quirks in probe",
    )

    old_fixup = """\t/* For the T100CHI/T90CHI keyboard dock */
\tif (drvdata->quirks & (QUIRK_T100CHI | QUIRK_T90CHI)) {
\t\tint rsize_orig;
\t\tint offs;

\t\tif (drvdata->quirks & QUIRK_T100CHI) {
\t\t\trsize_orig = 403;
\t\t\toffs = 388;
\t\t} else {
\t\t\trsize_orig = 306;
\t\t\toffs = 291;
\t\t}

\t\t/*
\t\t * Change Usage (76h) to Usage Minimum (00h), Usage Maximum
\t\t * (FFh) and clear the flags in the Input() byte.
\t\t * Note the descriptor has a bogus 0 byte at the end so we
\t\t * only need 1 extra byte.
\t\t */
\t\tif (*rsize == rsize_orig &&
\t\t\trdesc[offs] == 0x09 && rdesc[offs + 1] == 0x76) {
\t\t\t__u8 *new_rdesc;

\t\t\tnew_rdesc = devm_kzalloc(&hdev->dev, rsize_orig + 1,
\t\t\t\t\t\t GFP_KERNEL);
\t\t\tif (!new_rdesc)
\t\t\t\treturn rdesc;

\t\t\thid_info(hdev, "Fixing up %s keyb report descriptor\\n",
\t\t\t\tdrvdata->quirks & QUIRK_T100CHI ?
\t\t\t\t"T100CHI" : "T90CHI");

\t\t\tmemcpy(new_rdesc, rdesc, rsize_orig);
\t\t\t*rsize = rsize_orig + 1;
\t\t\trdesc = new_rdesc;

\t\t\tmemmove(rdesc + offs + 4, rdesc + offs + 2, 12);
\t\t\trdesc[offs] = 0x19;
\t\t\trdesc[offs + 1] = 0x00;
\t\t\trdesc[offs + 2] = 0x29;
\t\t\trdesc[offs + 3] = 0xff;
\t\t\trdesc[offs + 14] = 0x00;
\t\t}
\t}"""

    new_fixup = """\t/* For the T100CHI/T90CHI dock and Zenbook Duo detachable keyboard */
\tif (drvdata->quirks & (QUIRK_T100CHI | QUIRK_T90CHI | QUIRK_ZENBOOK_DUO_KEYBOARD)) {
\t\tint rsize_orig;
\t\tint offs;

\t\tif (drvdata->quirks & QUIRK_T100CHI) {
\t\t\trsize_orig = 403;
\t\t\toffs = 388;
\t\t} else if (drvdata->quirks & QUIRK_T90CHI) {
\t\t\trsize_orig = 306;
\t\t\toffs = 291;
\t\t} else if (drvdata->quirks & QUIRK_ZENBOOK_DUO_KEYBOARD) {
\t\t\tif (hid_is_usb(hdev)) {
\t\t\t\trsize_orig = 90;
\t\t\t\toffs = 66;
\t\t\t} else {
\t\t\t\trsize_orig = 257;
\t\t\t\toffs = 176;
\t\t\t}
\t\t}

\t\t/*
\t\t * Change Usage (76h) to Usage Minimum (00h), Usage Maximum
\t\t * (FFh) and clear the flags in the Input() byte.
\t\t */
\t\tif (*rsize == rsize_orig &&
\t\t\trdesc[offs] == 0x09 && rdesc[offs + 1] == 0x76) {
\t\t\t__u8 *new_rdesc;

\t\t\tif (drvdata->quirks & QUIRK_ZENBOOK_DUO_KEYBOARD) {
\t\t\t\twhile (*rsize > 0 && rdesc[*rsize - 1] == 0)
\t\t\t\t\t--*rsize;

\t\t\t\tnew_rdesc = kmemdup(rdesc, *rsize + 2, GFP_KERNEL);
\t\t\t\tif (!new_rdesc)
\t\t\t\t\treturn rdesc;

\t\t\t\t*rsize += 2;
\t\t\t\trdesc = new_rdesc;
\t\t\t} else {
\t\t\t\tnew_rdesc = devm_kzalloc(&hdev->dev, rsize_orig + 1,
\t\t\t\t\t\t\t GFP_KERNEL);
\t\t\t\tif (!new_rdesc)
\t\t\t\t\treturn rdesc;

\t\t\t\tmemcpy(new_rdesc, rdesc, rsize_orig);
\t\t\t\t*rsize = rsize_orig + 1;
\t\t\t\trdesc = new_rdesc;
\t\t\t}

\t\t\thid_info(hdev, "Fixing up %s keyb report descriptor\\n",
\t\t\t\tdrvdata->quirks & QUIRK_T100CHI ? "T100CHI" :
\t\t\t\tdrvdata->quirks & QUIRK_T90CHI ? "T90CHI" : "ZENBOOK DUO");

\t\t\tmemmove(rdesc + offs + 4, rdesc + offs + 2, 12);
\t\t\trdesc[offs] = 0x19;
\t\t\trdesc[offs + 1] = 0x00;
\t\t\trdesc[offs + 2] = 0x29;
\t\t\trdesc[offs + 3] = 0xff;
\t\t\trdesc[offs + 14] = 0x00;
\t\t}
\t}

\tif ((drvdata->quirks & QUIRK_ZENBOOK_DUO_KEYBOARD) &&
\t    hid_is_usb(hdev) &&
\t    to_usb_interface(hdev->dev.parent)->altsetting->desc.bInterfaceNumber == 4) {
\t\t__u8 *new_rdesc;
\t\tsize_t new_size = *rsize + sizeof(asus_fake_keyboard_rdesc);

\t\tnew_rdesc = devm_kzalloc(&hdev->dev, new_size, GFP_KERNEL);
\t\tif (!new_rdesc)
\t\t\treturn rdesc;

\t\thid_info(hdev, "Injecting virtual Zenbook Duo keyboard usage page\\n");

\t\tmemcpy(new_rdesc, asus_fake_keyboard_rdesc, sizeof(asus_fake_keyboard_rdesc));
\t\tmemcpy(new_rdesc + sizeof(asus_fake_keyboard_rdesc), rdesc, *rsize);

\t\t*rsize = new_size;
\t\trdesc = new_rdesc;
\t}"""

    text = replace_once(old_fixup, new_fixup, text, "report_fixup zenbook")

    if "drvdata->fn_lock_sync_work.func" not in text:
        text = replace_once(
            "\tif (drvdata->quirks & QUIRK_HID_FN_LOCK)\n"
            "\t\tcancel_work_sync(&drvdata->fn_lock_sync_work);\n\n"
            "\thid_hw_stop(hdev);\n"
            "}",
            "\tif (drvdata->fn_lock_sync_work.func)\n"
            "\t\tcancel_work_sync(&drvdata->fn_lock_sync_work);\n\n"
            "\thid_hw_stop(hdev);\n"
            "}",
            text,
            "asus_remove fn_lock cancel guard",
        )

    text = insert_after(
        r"\t\{ HID_DEVICE\(BUS_USB, HID_GROUP_GENERIC,\n\t\tUSB_VENDOR_ID_ASUSTEK, USB_DEVICE_ID_ASUSTEK_T101HA_KEYBOARD\) \},\n",
        DEVICE_ENTRIES,
        text,
    )

    dst.write_text(text)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("kernel_src", type=Path, help="Path to /usr/src/linux-* tree")
    parser.add_argument("output", type=Path, help="Output hid-asus.c path")
    args = parser.parse_args()

    src = args.kernel_src / "drivers/hid/hid-asus.c"
    if not src.is_file():
        print(f"missing {src}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    port_hid_asus(src, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
