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

FN_LOCK_MODULE_BLOCK = """
/* Pin Fn-lock layout (UX8406 Mode B = fn_lock false = Fn+F-row actions). */
static int fn_lock_default = -1;
module_param(fn_lock_default, int, 0644);
MODULE_PARM_DESC(fn_lock_default,
		 "Initial Fn-lock: -1=DMI default, 0=Fn layer (Zenbook Mode B), 1=plain F-keys (Mode A)");

static bool fn_lock_allow_toggle = true;
module_param(fn_lock_allow_toggle, bool, 0644);
MODULE_PARM_DESC(fn_lock_allow_toggle,
		 "Allow Fn+Esc / vendor 0x4e to toggle Fn-lock");

static bool asus_fn_lock_default_for_device(struct hid_device *hdev,
					    struct asus_drvdata *drvdata)
{
	if (fn_lock_default >= 0)
		return !!fn_lock_default;

	if ((drvdata->quirks & QUIRK_ZENBOOK_DUO_KEYBOARD) &&
	    dmi_check_system(ux8406_hid_kbd_backlight_dmi))
		return false;

	return true;
}
"""

FN_ROW_POLICY_PARAMS = """
/*
 * Per-key Fn-row merge on UX8406 USB (Mode B firmware baseline):
 *   plain F1-F3 → if3 KEY_VOLUME* (often ignored by mixer)
 *   Fn+F1-F3    → if0 KEY_F1-F3 (+ EC volume)
 *   plain F5/F6 → if4 vendor 0x10/0x20 brightness
 *   Fn+F5/F6    → if0 KEY_F5/F6
 *   plain F4    → if4 vendor 0xc7 kbd BL
 *   Fn+F4       → if0 KEY_F4
 *   plain F7    → if0 Win+P (Plasma display switch) and/or vendor 0x35
 *   plain F12   → if4 vendor 0x86 MyASUS / ASUS key (KEY_PROG1)
 *
 * Bits 0-11: F1-F12, bit 12: Esc.
 * F1-F3 (bits 0-2): bit set → re-emit plain media on if0; bit clear → plain→KEY_Fn.
 * F4-F12 (bits 3-11): bit clear → swap (plain KEY_Fn, Fn+F → special);
 *                       bit set → keep Mode B (plain special, Fn KEY_Fn).
 *
 * Recommended docked: fn_row_policy=7 (0x07) — F1-F3 as-is, F4-F12 swapped.
 */
static u32 fn_row_policy;
module_param(fn_row_policy, uint, 0644);
MODULE_PARM_DESC(fn_row_policy,
		 "Fn-row bitmask: F1-F3 plain-sim / F4-F12 Fn-sim (see kernel/README)");

static struct asus_kbd_leds *zenbook_duo_vendor_leds;
static struct hid_device *zenbook_duo_consumer_hdev;
static struct hid_device *zenbook_duo_main_hdev;
static struct hid_device *zenbook_duo_vendor_hdev;

static u8 zenbook_if0_modifiers;
static bool zenbook_super_key_down;
static bool zenbook_f56_vendor_pass_pending;
static bool zenbook_f56_vendor_pass_down;
static bool zenbook_f56_vendor_pass_gui;
static bool zenbook_f56_plain_vendor_burst;
static bool zenbook_f4_if0_usage_down;
static bool zenbook_f4_press_handled;
static bool zenbook_f4_bl_stepped;
static bool zenbook_f4_hw_key_seen;

static int zenbook_fn_row_policy_f4_event(struct hid_device *hdev,
					  struct hid_usage *usage, __s32 value);
static int zenbook_fn_row_f56_vendor_event(struct hid_device *hdev,
					   struct hid_usage *usage, __s32 value);
static int zenbook_fn_row_fn_f13_event(struct hid_device *hdev,
				       struct hid_usage *usage, __s32 value);
static int zenbook_fn_row_fn_f56_event(struct hid_device *hdev,
				       struct hid_usage *usage, __s32 value);
static int zenbook_fn_row_super_track(struct hid_device *hdev,
				      struct asus_drvdata *drvdata,
				      struct hid_usage *usage, __s32 value);
static int zenbook_fn_row_policy_raw(struct hid_device *hdev,
				     struct asus_drvdata *drvdata,
				     u8 *data, int size);
static int zenbook_fn_row_policy_vendor_raw(struct hid_device *hdev,
					    u8 *data, int size);
static int zenbook_fn_row_policy_consumer_raw(struct hid_device *hdev,
					      u8 *data, int size);
"""

FN_ROW_POLICY_IMPL = """
#define ZENBOOK_HID_F1\t\t0x3a
#define ZENBOOK_HID_F4\t\t0x3d
#define ZENBOOK_HID_F5\t\t0x3e
#define ZENBOOK_HID_F6\t\t0x3f
#define ZENBOOK_HID_F12\t\t0x45
#define ZENBOOK_HID_ESC\t\t0x29
#define ZENBOOK_HID_P\t\t0x13
#define ZENBOOK_IF0_MOD_CTRL\t(BIT(0) | BIT(4))
#define ZENBOOK_IF0_MOD_ALT\t(BIT(2) | BIT(6))
#define ZENBOOK_IF0_MOD_GUI\t(BIT(3) | BIT(7))
/* Alt/Ctrl/Meta+F must stay KEY_Fn for the desktop — not Fn-row specials. */
#define ZENBOOK_IF0_MOD_DESKTOP\t(ZENBOOK_IF0_MOD_CTRL | ZENBOOK_IF0_MOD_ALT | \
				 ZENBOOK_IF0_MOD_GUI)

/*
 * Unused after Mode B swap (policy bit clear → plain KEY_Fn / Fn special).
 * Enable to revive deferred vendor→KEY_F4 inject, stepped kbd BL, or F4–F12
 * plain passthrough helpers.
 */
/* #define ZENBOOK_FN_ROW_LEGACY_F4 */

#ifdef ZENBOOK_FN_ROW_LEGACY_F4
#define ZENBOOK_F4_VENDOR_DEFER_MS\t25

static void zenbook_f4_vendor_dw_fn(struct work_struct *work);

static DECLARE_DELAYED_WORK(zenbook_f4_vendor_dw, zenbook_f4_vendor_dw_fn);

static bool zenbook_fn_row_usage_is_f4(struct hid_usage *usage)
{
	if (usage->code == KEY_F4)
		return true;

	return (usage->hid & HID_USAGE_PAGE) == HID_UP_KEYBOARD &&
	       (usage->hid & HID_USAGE) == ZENBOOK_HID_F4;
}

static void zenbook_f4_cancel_vendor_dw(void)
{
	cancel_delayed_work_sync(&zenbook_f4_vendor_dw);
}

static void zenbook_f4_vendor_arm(void)
{
	cancel_delayed_work_sync(&zenbook_f4_vendor_dw);
	schedule_delayed_work(&zenbook_f4_vendor_dw,
			    msecs_to_jiffies(ZENBOOK_F4_VENDOR_DEFER_MS));
}
#endif /* ZENBOOK_FN_ROW_LEGACY_F4 */

static void zenbook_fn_row_emit_win_p(struct hid_device *hdev);

static bool zenbook_is_duo_usb_if(struct hid_device *hdev, unsigned int ifnum_want)
{
	struct usb_interface *intf;
	struct usb_device *udev;

	if (!hid_is_usb(hdev))
		return false;

	intf = to_usb_interface(hdev->dev.parent);
	if (intf->altsetting->desc.bInterfaceNumber != ifnum_want)
		return false;

	udev = interface_to_usbdev(intf);
	return le16_to_cpu(udev->descriptor.idProduct) ==
		USB_DEVICE_ID_ASUSTEK_ZENBOOK_DUO_KEYBOARD;
}

static bool zenbook_is_duo_main_keyboard(struct hid_device *hdev,
					 struct asus_drvdata *drvdata)
{
	(void)drvdata;
	return zenbook_is_duo_usb_if(hdev, 0);
}

static bool zenbook_is_duo_consumer_if3(struct hid_device *hdev)
{
	return zenbook_is_duo_usb_if(hdev, 3);
}

static bool zenbook_is_duo_vendor_if4(struct hid_device *hdev)
{
	return zenbook_is_duo_usb_if(hdev, 4);
}

static int zenbook_fn_row_hid_usage_bit(u8 usage)
{
	if (usage >= ZENBOOK_HID_F1 && usage <= ZENBOOK_HID_F12)
		return usage - ZENBOOK_HID_F1;
	if (usage == ZENBOOK_HID_ESC)
		return 12;

	return -1;
}

static bool zenbook_fn_row_report_has_usage(const u8 *data, int size, u8 usage)
{
	int i;

	for (i = 0; i < size; i++) {
		if (data[i] == usage)
			return true;
	}
	return false;
}

static bool zenbook_fn_row_is_f13(int bit)
{
	return bit >= 0 && bit <= 2;
}

/* True when Alt/Ctrl/Meta held — do not apply bare Fn→special remaps. */
static bool zenbook_if0_desktop_mods(void)
{
	return !!(zenbook_if0_modifiers & ZENBOOK_IF0_MOD_DESKTOP);
}

static unsigned int zenbook_fn_row_f13_media_key(int bit)
{
	switch (bit) {
	case 0:
		return KEY_MUTE;
	case 1:
		return KEY_VOLUMEDOWN;
	default:
		return KEY_VOLUMEUP;
	}
}

static void zenbook_fn_row_emit_on_hdev(struct hid_device *hdev,
					unsigned int keycode)
{
	struct hid_input *hidinput;

	if (!hdev)
		return;

	list_for_each_entry(hidinput, &hdev->inputs, list) {
		if (!hidinput->input)
			continue;
		input_set_capability(hidinput->input, EV_KEY, keycode);
		input_report_key(hidinput->input, keycode, 1);
		input_sync(hidinput->input);
		input_report_key(hidinput->input, keycode, 0);
		input_sync(hidinput->input);
		return;
	}
}

/* UX8406 plain F7 firmware synthesizes Win+P for Plasma display switch. */
static void zenbook_fn_row_emit_win_p(struct hid_device *hdev)
{
	struct hid_input *hidinput;

	if (!hdev)
		return;

	list_for_each_entry(hidinput, &hdev->inputs, list) {
		if (!hidinput->input)
			continue;
		input_set_capability(hidinput->input, EV_KEY, KEY_LEFTMETA);
		input_set_capability(hidinput->input, EV_KEY, KEY_P);
		input_report_key(hidinput->input, KEY_LEFTMETA, 1);
		input_report_key(hidinput->input, KEY_P, 1);
		input_sync(hidinput->input);
		input_report_key(hidinput->input, KEY_P, 0);
		input_report_key(hidinput->input, KEY_LEFTMETA, 0);
		input_sync(hidinput->input);
		return;
	}
}

/* Meta+F4 uses vendor inject; other Meta+F-row → KEY_Fn on if0. */
static void zenbook_fn_row_meta_emit_fkey(struct hid_device *if0, int bit)
{
	if (!if0 || bit < 0 || bit > 11 || bit == 3)
		return;

	zenbook_fn_row_emit_on_hdev(if0, KEY_F1 + bit);
}

static int zenbook_fn_row_super_track(struct hid_device *hdev,
				      struct asus_drvdata *drvdata,
				      struct hid_usage *usage, __s32 value)
{
	if (!usage || usage->type != EV_KEY)
		return 0;
	if (!zenbook_is_duo_main_keyboard(hdev, drvdata))
		return 0;

	switch (usage->code) {
	case KEY_LEFTMETA:
	case KEY_RIGHTMETA:
		zenbook_super_key_down = !!value;
		break;
	}

	return 0;
}

static bool zenbook_f56_usage_is_f5(struct hid_usage *usage)
{
	if (usage->type == EV_KEY && usage->code == KEY_BRIGHTNESSDOWN)
		return true;

	return (usage->hid & HID_USAGE_PAGE) == HID_UP_ASUSVENDOR &&
	       (usage->hid & HID_USAGE) == 0x10;
}

static bool zenbook_f56_usage_is_f6(struct hid_usage *usage)
{
	if (usage->type == EV_KEY && usage->code == KEY_BRIGHTNESSUP)
		return true;

	return (usage->hid & HID_USAGE_PAGE) == HID_UP_ASUSVENDOR &&
	       (usage->hid & HID_USAGE) == 0x20;
}

/*
 * Vendor 0x10/0x20 with byte0 GUI (Super or Fn). Polarity per key:
 *   F5: Meta=DOWN v1, Fn=DOWN v0 (+ spurious UP)
 *   F6: Meta=UP v1,   Fn=UP v0   (+ spurious DOWN)
 */
static int zenbook_fn_row_f56_vendor_event(struct hid_device *hdev,
					   struct hid_usage *usage, __s32 value)
{
	int bit;

	if (!zenbook_f56_vendor_pass_pending || !zenbook_is_duo_vendor_if4(hdev))
		return 0;

	if (!zenbook_f56_vendor_pass_gui) {
		/* Plain (v=1) or Fn without byte0 GUI latched at vendor raw time (v=0). */
		if (zenbook_f56_vendor_pass_down) {
			if (zenbook_f56_usage_is_f5(usage) && value == 1) {
				zenbook_f56_vendor_pass_pending = false;
				return 0;
			}
			if (zenbook_f56_usage_is_f5(usage) && value == 0) {
				zenbook_fn_row_emit_on_hdev(hdev, KEY_BRIGHTNESSDOWN);
				zenbook_f56_vendor_pass_pending = false;
				return 1;
			}
			if (zenbook_f56_usage_is_f6(usage)) {
				zenbook_f56_vendor_pass_pending = false;
				return 1;
			}
		} else {
			if (zenbook_f56_usage_is_f6(usage) && value == 1) {
				zenbook_f56_vendor_pass_pending = false;
				return 0;
			}
			if (zenbook_f56_usage_is_f6(usage) && value == 0) {
				zenbook_fn_row_emit_on_hdev(hdev, KEY_BRIGHTNESSUP);
				zenbook_f56_vendor_pass_pending = false;
				return 1;
			}
			if (zenbook_f56_usage_is_f5(usage)) {
				zenbook_f56_vendor_pass_pending = false;
				return 1;
			}
		}
		return 0;
	}

	if (zenbook_f56_vendor_pass_down) {
		if (zenbook_f56_usage_is_f5(usage) && value == 1) {
			bit = 4;
			goto meta_emit;
		}
		if (zenbook_f56_usage_is_f5(usage) && value == 0) {
			zenbook_fn_row_emit_on_hdev(hdev, KEY_BRIGHTNESSDOWN);
			zenbook_f56_vendor_pass_pending = false;
			return 1;
		}
		if (zenbook_f56_usage_is_f6(usage)) {
			zenbook_f56_vendor_pass_pending = false;
			return 1;
		}
	} else {
		if (zenbook_f56_usage_is_f6(usage) && value == 1) {
			bit = 5;
			goto meta_emit;
		}
		if (zenbook_f56_usage_is_f6(usage) && value == 0) {
			zenbook_fn_row_emit_on_hdev(hdev, KEY_BRIGHTNESSUP);
			zenbook_f56_vendor_pass_pending = false;
			return 1;
		}
		if (zenbook_f56_usage_is_f5(usage)) {
			zenbook_f56_vendor_pass_pending = false;
			return 1;
		}
	}

	return 0;

meta_emit:
	zenbook_f56_vendor_pass_pending = false;
	zenbook_fn_row_meta_emit_fkey(zenbook_duo_main_hdev ?: hdev, bit);
	return 1;
}

static int zenbook_fn_row_fn_f13_event(struct hid_device *hdev,
				       struct hid_usage *usage, __s32 value)
{
	int bit;

	/* Parsed if3 volume: only used when bit clear (plain → KEY_Fn). */
	if (!fn_row_policy || !zenbook_is_duo_consumer_if3(hdev))
		return 0;
	if (zenbook_if0_desktop_mods())
		return 0;

	switch (usage->code) {
	case KEY_MUTE:
		bit = 0;
		break;
	case KEY_VOLUMEDOWN:
		bit = 1;
		break;
	case KEY_VOLUMEUP:
		bit = 2;
		break;
	default:
		return 0;
	}

	if (fn_row_policy & BIT(bit))
		return 0;

	if (value && zenbook_duo_main_hdev)
		zenbook_fn_row_emit_on_hdev(zenbook_duo_main_hdev, KEY_F1 + bit);

	return 1;
}

static int zenbook_fn_row_fn_f56_event(struct hid_device *hdev,
				       struct hid_usage *usage, __s32 value)
{
	struct asus_drvdata *drvdata = hid_get_drvdata(hdev);
	struct hid_device *vh = zenbook_duo_vendor_hdev ?: hdev;
	int bit = -1;
	unsigned int special = 0;

	if (!fn_row_policy)
		return 0;
	if (!zenbook_is_duo_main_keyboard(hdev, drvdata))
		return 0;
	/* Alt+F4 must close windows — not kbd BL; same for Ctrl/Meta+F*. */
	if (zenbook_if0_desktop_mods())
		return 0;

	/*
	 * Bit clear on F4–F12: Mode B swap — Fn+F (if0 KEY_Fn) → hardware special.
	 * Plain specials are swallowed in vendor_raw and re-emitted as KEY_Fn.
	 */
	switch (usage->code) {
	case KEY_F4:
		bit = 3;
		break;
	case KEY_F5:
	case KEY_BRIGHTNESSDOWN:
		bit = 4;
		special = KEY_BRIGHTNESSDOWN;
		break;
	case KEY_F6:
	case KEY_BRIGHTNESSUP:
		bit = 5;
		special = KEY_BRIGHTNESSUP;
		break;
	case KEY_F7:
	case KEY_DISPLAY_OFF:
	case KEY_SWITCHVIDEOMODE:
		bit = 6;
		special = KEY_SWITCHVIDEOMODE; /* fallback; prefer Win+P below */
		break;
	case KEY_F12:
	case KEY_PROG1:
		bit = 11;
		special = KEY_PROG1; /* MyASUS / ASUS key (vendor 0x86) */
		break;
	default:
		return 0;
	}

	if (fn_row_policy & BIT(bit))
		return 0;

	/* Echo of plain vendor→KEY_Fn inject: swallow, do not re-special. */
	if (zenbook_f56_plain_vendor_burst &&
	    (usage->code == KEY_F4 || usage->code == KEY_F5 ||
	     usage->code == KEY_F6 || usage->code == KEY_F7 ||
	     usage->code == KEY_F12)) {
		if (value)
			zenbook_f56_plain_vendor_burst = false;
		return 1;
	}

	/* Special keycode on if0 (should not happen often): swallow. */
	if (usage->code == KEY_BRIGHTNESSDOWN ||
	    usage->code == KEY_BRIGHTNESSUP ||
	    usage->code == KEY_DISPLAY_OFF ||
	    usage->code == KEY_SWITCHVIDEOMODE ||
	    usage->code == KEY_PROG1 ||
	    usage->code == KEY_KBDILLUMTOGGLE) {
		return 1;
	}

	if (!value)
		return 1;

	/* Fn+F4: real kbd BL toggle via asus-wmi HID listener. */
	if (bit == 3) {
		asus_hid_event(ASUS_EV_BRTTOGGLE);
		return 1;
	}

	/* Fn+F7: same Win+P burst firmware uses on plain F7. */
	if (bit == 6) {
		zenbook_fn_row_emit_win_p(hdev);
		return 1;
	}

	if (special)
		zenbook_fn_row_emit_on_hdev(bit == 11 ? hdev : vh, special);
	return 1;
}

static void zenbook_fn_row_emit_f4_once(struct hid_device *if0)
{
	if (!if0 || zenbook_f4_press_handled)
		return;

	zenbook_f4_press_handled = true;
	zenbook_fn_row_emit_on_hdev(if0, KEY_F4);
}

#ifdef ZENBOOK_FN_ROW_LEGACY_F4
static void zenbook_f4_vendor_dw_fn(struct work_struct *work)
{
	(void)work;

	if (zenbook_f4_if0_usage_down || zenbook_f4_hw_key_seen ||
	    zenbook_f4_press_handled)
		return;

	/* Plain F4 without if0 0x3d (vendor-only firmware path). */
	if (zenbook_duo_main_hdev)
		zenbook_fn_row_emit_f4_once(zenbook_duo_main_hdev);
}
#endif /* ZENBOOK_FN_ROW_LEGACY_F4 */

static void zenbook_fn_row_f4_press_end(void)
{
	zenbook_f4_press_handled = false;
	zenbook_f4_if0_usage_down = false;
	zenbook_f4_bl_stepped = false;
	zenbook_f4_hw_key_seen = false;
}

#ifdef ZENBOOK_FN_ROW_LEGACY_F4
static void zenbook_fn_row_step_backlight(void)
{
	struct asus_kbd_leds *led = zenbook_duo_vendor_leds;
	struct asus_drvdata *drvdata;
	unsigned long flags;
	unsigned int next, cur;

	if (!led && zenbook_duo_vendor_hdev) {
		drvdata = hid_get_drvdata(zenbook_duo_vendor_hdev);
		if (drvdata) {
			led = drvdata->kbd_backlight;
			if (led)
				zenbook_duo_vendor_leds = led;
		}
	}
	if (!led)
		return;

	spin_lock_irqsave(&led->lock, flags);
	cur = led->brightness;
	next = cur >= 3 ? 0 : cur + 1;
	spin_unlock_irqrestore(&led->lock, flags);

	asus_kbd_backlight_set(&led->listener, next);
}

static void zenbook_fn_row_f4_step_once(void)
{
	if (zenbook_f4_bl_stepped)
		return;

	zenbook_f4_bl_stepped = true;
	zenbook_fn_row_step_backlight();
}

static void zenbook_fn_row_f412_plain_passthrough(struct hid_device *if0, u8 usage)
{
	int bit = zenbook_fn_row_hid_usage_bit(usage);

	if (bit < 3)
		return;

	zenbook_fn_row_emit_on_hdev(if0, KEY_F1 + bit);
}
#endif /* ZENBOOK_FN_ROW_LEGACY_F4 */

static int zenbook_fn_row_policy_consumer_raw(struct hid_device *hdev,
					      u8 *data, int size)
{
	static bool f1_down, f2_down, f3_down;
	int bit;
	bool down, rising;
	struct hid_device *if0 = zenbook_duo_main_hdev;

	if (!fn_row_policy || !zenbook_is_duo_consumer_if3(hdev) || size < 2)
		return 0;

	zenbook_duo_consumer_hdev = hdev;

	/* if3 consumer: 03 e2/ea/e9 (mute / vol- / vol+). */
	if (data[0] != 0x03)
		return 0;

	if (data[1] == 0x00) {
		f1_down = false;
		f2_down = false;
		f3_down = false;
		return 0;
	}

	switch (data[1]) {
	case 0xe2:
		bit = 0;
		break;
	case 0xea:
		bit = 1;
		break;
	case 0xe9:
		bit = 2;
		break;
	default:
		return 0;
	}

	down = size < 3 || data[2] == 0x00;
	switch (bit) {
	case 0:
		rising = down && !f1_down;
		f1_down = down;
		break;
	case 1:
		rising = down && !f2_down;
		f2_down = down;
		break;
	default:
		rising = down && !f3_down;
		f3_down = down;
		break;
	}

	if (zenbook_if0_modifiers & ZENBOOK_IF0_MOD_GUI) {
		/* Meta+plain F1–F3: if3 media → KEY_Fn for workspace bindings. */
		if (rising && if0)
			zenbook_fn_row_meta_emit_fkey(if0, bit);
		return -1;
	}

	if (zenbook_if0_modifiers & (ZENBOOK_IF0_MOD_ALT | ZENBOOK_IF0_MOD_CTRL)) {
		/*
		 * Mode B: Alt/Ctrl+F1–F3 still emit if3 media. Desktop wants
		 * Alt+F2 (Plasma launcher), etc. — emit KEY_Fn; modifiers stay on if0.
		 */
		if (rising && if0)
			zenbook_fn_row_emit_on_hdev(if0, KEY_F1 + bit);
		return -1;
	}

	if (fn_row_policy & BIT(bit)) {
		/*
		 * Bit set: Mode B plain media on if3 is often ignored by the mixer.
		 * Re-emit on if0 (main keyboard) and swallow the dead if3 event.
		 */
		if (rising && if0)
			zenbook_fn_row_emit_on_hdev(if0,
						    zenbook_fn_row_f13_media_key(bit));
		return -1;
	}

	/* Bit clear: plain if3 media → KEY_F1–F3 on if0. */
	if (rising && if0)
		zenbook_fn_row_emit_on_hdev(if0, KEY_F1 + bit);
	return -1;
}

static int zenbook_fn_row_policy_raw(struct hid_device *hdev,
				     struct asus_drvdata *drvdata,
				     u8 *data, int size)
{
	static u8 prev[8];
	static int prev_len;
	int i, bit, swallow;
	u8 usage;
	bool rising, f4_now, f4_rising;

	if (!fn_row_policy || !zenbook_is_duo_main_keyboard(hdev, drvdata) || size < 1)
		return 0;

	zenbook_duo_main_hdev = hdev;

	if (size >= 1)
		zenbook_if0_modifiers = data[0];

	f4_now = (fn_row_policy & BIT(3)) &&
		 zenbook_fn_row_report_has_usage(data, size, ZENBOOK_HID_F4);
	f4_rising = f4_now && !zenbook_f4_if0_usage_down;
	zenbook_f4_if0_usage_down = f4_now;

	/* Meta / Super + F-row (F4 handled in vendor raw). */
	if (data[0] & ZENBOOK_IF0_MOD_GUI) {
		int meta_swallow = 0;
		bool has_p = zenbook_fn_row_report_has_usage(data, size, ZENBOOK_HID_P);
		bool only_p = has_p;
		int ki;

		/*
		 * Plain F7: firmware sends Win+P (GUI + only 'P'). Remap to KEY_F7.
		 * Fn+F7 re-injects Win+P via input_report (bypasses this path).
		 * Side effect: real Meta+P on this keyboard also becomes KEY_F7;
		 * use Fn+F7 for Plasma display switch.
		 */
		for (ki = 2; ki < size && ki < 8; ki++) {
			if (data[ki] == 0x00)
				continue;
			if (data[ki] != ZENBOOK_HID_P) {
				only_p = false;
				break;
			}
		}
		if (!(fn_row_policy & BIT(6)) && only_p) {
			zenbook_fn_row_emit_on_hdev(hdev, KEY_F7);
			if (size <= (int)sizeof(prev)) {
				memcpy(prev, data, size);
				prev_len = size;
			} else {
				prev_len = 0;
			}
			return -1;
		}

		for (i = 2; i < size && i < 8; i++) {
			usage = data[i];
			bit = zenbook_fn_row_hid_usage_bit(usage);
			if (bit < 0 || bit > 11 || bit == 3)
				continue;

			rising = !zenbook_fn_row_report_has_usage(prev, prev_len, usage) &&
				 zenbook_fn_row_report_has_usage(data, size, usage);
			if (rising) {
				zenbook_fn_row_meta_emit_fkey(hdev, bit);
				meta_swallow = 1;
			}
		}

		if (size <= (int)sizeof(prev)) {
			memcpy(prev, data, size);
			prev_len = size;
		} else {
			prev_len = 0;
		}

		return meta_swallow ? -1 : 0;
	}

	swallow = 0;
	for (i = 2; i < size && i < 8; i++) {
		usage = data[i];
		bit = zenbook_fn_row_hid_usage_bit(usage);
		if (bit < 0 || bit > 11)
			continue;

		rising = !zenbook_fn_row_report_has_usage(prev, prev_len, usage) &&
			 zenbook_fn_row_report_has_usage(data, size, usage);

		if (zenbook_fn_row_is_f13(bit)) {
			/*
			 * Mode B: if0 F1–F3 is Fn+F1–F3 → KEY_Fn. Pass through.
			 * (Bit clear does not add media on Fn; EC may still volume.)
			 */
			(void)rising;
		} else if (bit >= 4 && bit <= 11 && !(fn_row_policy & BIT(bit))) {
			/* Bit clear: Fn+F5+ on if0 KEY_Fn → redirect in fn_f56_event. */
			if (zenbook_f56_plain_vendor_burst && rising) {
				zenbook_f56_plain_vendor_burst = false;
				swallow = 1;
			}
		} else if (bit >= 4 && bit <= 11 && (fn_row_policy & BIT(bit))) {
			/* Bit set: keep Mode B plain specials; if0 KEY_Fn is Fn chord. */
			(void)rising;
		}
	}

	/*
	 * F4 bit set: keep Mode B (Fn+F4 = KEY_F4 on if0). Do not step BL here.
	 * f4_now only tracks if0 0x3d for vendor/Meta coordination.
	 */
	(void)f4_rising;
	if (!f4_now && zenbook_f4_press_handled)
		zenbook_fn_row_f4_press_end();

	if (size <= (int)sizeof(prev)) {
		memcpy(prev, data, size);
		prev_len = size;
	} else {
		prev_len = 0;
	}

	return swallow ? -1 : 0;
}

static int zenbook_fn_row_policy_vendor_raw(struct hid_device *hdev,
					    u8 *data, int size)
{
	static bool f4_vendor_down;
	static bool f5_vendor_down, f6_vendor_down;
	static bool f7_vendor_down, f12_vendor_down;

	if (!fn_row_policy || !zenbook_is_duo_vendor_if4(hdev))
		return 0;

	zenbook_duo_vendor_hdev = hdev;
	{
		struct asus_drvdata *vdrv = hid_get_drvdata(hdev);

		if (vdrv && vdrv->kbd_backlight)
			zenbook_duo_vendor_leds = vdrv->kbd_backlight;
	}

	if (size < 2 || data[0] != 0x5a)
		return 0;

	/* Trailer 5a00 ends vendor key burst. */
	if (data[1] == 0x00) {
		f5_vendor_down = false;
		f6_vendor_down = false;
		f7_vendor_down = false;
		f12_vendor_down = false;
		zenbook_f56_plain_vendor_burst = false;
	}

	/*
	 * Plain Mode B specials on if4 (bit clear → swap to KEY_Fn).
	 * 0x10/0x20 F5/F6 brightness, 0xc7 F4 kbd BL, 0x35 F7 display,
	 * 0x86 F12 MyASUS / ASUS key.
	 */
	if (data[1] == 0x10 || data[1] == 0x20 || data[1] == 0xc7 ||
	    data[1] == 0x35 || data[1] == 0x86) {
		bool down = size < 3 || data[2] == 0x00;
		bool rising;
		int bit;
		unsigned int fkey;

		switch (data[1]) {
		case 0xc7:
			bit = 3;
			fkey = KEY_F4;
			rising = down && !f4_vendor_down;
			f4_vendor_down = down;
			break;
		case 0x10:
			bit = 4;
			fkey = KEY_F5;
			rising = down && !f5_vendor_down;
			f5_vendor_down = down;
			break;
		case 0x20:
			bit = 5;
			fkey = KEY_F6;
			rising = down && !f6_vendor_down;
			f6_vendor_down = down;
			break;
		case 0x35:
			bit = 6;
			fkey = KEY_F7;
			rising = down && !f7_vendor_down;
			f7_vendor_down = down;
			break;
		default: /* 0x86 MyASUS */
			bit = 11;
			fkey = KEY_F12;
			rising = down && !f12_vendor_down;
			f12_vendor_down = down;
			break;
		}

		if (zenbook_if0_modifiers & ZENBOOK_IF0_MOD_GUI) {
			if (bit == 3) {
				if (down && rising && zenbook_duo_main_hdev)
					zenbook_fn_row_emit_f4_once(zenbook_duo_main_hdev);
				if (!down)
					zenbook_fn_row_f4_press_end();
				return -1;
			}
			if (down && (bit == 4 || bit == 5)) {
				zenbook_f56_vendor_pass_pending = true;
				zenbook_f56_vendor_pass_down = (data[1] == 0x10);
				zenbook_f56_vendor_pass_gui = true;
				return 0;
			}
			if (down && rising && zenbook_duo_main_hdev)
				zenbook_fn_row_emit_on_hdev(zenbook_duo_main_hdev, fkey);
			return -1;
		}

		if (zenbook_if0_modifiers & (ZENBOOK_IF0_MOD_ALT | ZENBOOK_IF0_MOD_CTRL)) {
			/* Alt/Ctrl+plain F*: Mode B vendor special → KEY_Fn for desktop. */
			if (rising && zenbook_duo_main_hdev)
				zenbook_fn_row_emit_on_hdev(zenbook_duo_main_hdev, fkey);
			if (bit == 3 && !down)
				zenbook_fn_row_f4_press_end();
			return -1;
		}

		/* Bit set: keep Mode B special on plain. */
		if (fn_row_policy & BIT(bit))
			return 0;

		/* Bit clear: plain special → KEY_Fn. */
		if (rising && zenbook_duo_main_hdev)
			zenbook_fn_row_emit_on_hdev(zenbook_duo_main_hdev, fkey);
		if (rising)
			zenbook_f56_plain_vendor_burst = true;
		if (bit == 3 && !down)
			zenbook_fn_row_f4_press_end();
		return -1;
	}

	if (data[1] == 0x00 && f4_vendor_down) {
		f4_vendor_down = false;
		zenbook_fn_row_f4_press_end();
	}

	return 0;
}

static int zenbook_fn_row_policy_f4_event(struct hid_device *hdev,
					  struct hid_usage *usage, __s32 value)
{
	struct asus_drvdata *drvdata = hid_get_drvdata(hdev);

	/* Bit 3 set = keep Mode B Fn+F4 as KEY_F4; no BL remap. */
	(void)hdev;
	(void)usage;
	(void)value;
	(void)drvdata;
	return 0;
}
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
        '#include <linux/module.h>\n#include <linux/platform_profile.h>\n#include "ux8406-ids.h"\n',
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

    text = insert_before(
        r"static int asus_event\(struct hid_device \*hdev, struct hid_field \*field,\n",
        DMI_AND_WMI_CHECK + FN_LOCK_MODULE_BLOCK + FN_ROW_POLICY_PARAMS,
        text,
    )

    text = insert_after(
        r"\tconst struct asus_touchpad_info \*tp;\n",
        HAS_VENDOR_FIELD,
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
\t\t\tif (drvdata->quirks & QUIRK_HID_FN_LOCK && fn_lock_allow_toggle) {
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

    # 7.0.12 stock had a tab on the blank line after drvdata; 7.1.3+ is plain \n\n.
    asus_event_hooks = (
        "\tstruct asus_drvdata *drvdata = hid_get_drvdata(hdev);\n\n"
        "\tzenbook_fn_row_super_track(hdev, drvdata, usage, value);\n\n"
        "\tif (zenbook_fn_row_policy_f4_event(hdev, usage, value))\n"
        "\t\treturn 1;\n\n"
        "\tif (zenbook_fn_row_fn_f13_event(hdev, usage, value))\n"
        "\t\treturn 1;\n\n"
        "\tif (zenbook_fn_row_f56_vendor_event(hdev, usage, value))\n"
        "\t\treturn 1;\n\n"
        "\tif (zenbook_fn_row_fn_f56_event(hdev, usage, value))\n"
        "\t\treturn 1;\n\n"
        "\tif ((usage->hid & HID_USAGE_PAGE) == HID_UP_ASUSVENDOR &&\n"
        "\t    (usage->hid & HID_USAGE) != 0x00 &&\n"
        "\t    (usage->hid & HID_USAGE) != 0xff && !usage->type) {\n"
        "\t\tswitch (usage->hid & HID_USAGE) {"
    )
    for blank in ("\n\t\n", "\n\n"):
        needle = (
            "\tstruct asus_drvdata *drvdata = hid_get_drvdata(hdev);"
            + blank
            + "\tif ((usage->hid & HID_USAGE_PAGE) == HID_UP_ASUSVENDOR &&\n"
            "\t    (usage->hid & HID_USAGE) != 0x00 &&\n"
            "\t    (usage->hid & HID_USAGE) != 0xff && !usage->type) {\n"
            "\t\tswitch (usage->hid & HID_USAGE) {"
        )
        if needle in text:
            text = text.replace(needle, asus_event_hooks, 1)
            break
    else:
        raise SystemExit("replace target not found (asus_event fn_row_policy first)")

    text = replace_once(
        """\t\tcase KEY_FN_ESC:
\t\t\tif (drvdata->quirks & QUIRK_HID_FN_LOCK) {
\t\t\t\tdrvdata->fn_lock = !drvdata->fn_lock;
\t\t\t\tschedule_work(&drvdata->fn_lock_sync_work);
\t\t\t}
\t\t\tbreak;""",
        """\t\tcase KEY_FN_ESC:
\t\t\tif (drvdata->quirks & QUIRK_HID_FN_LOCK) {
\t\t\t\tif (fn_lock_allow_toggle) {
\t\t\t\t\tdrvdata->fn_lock = !drvdata->fn_lock;
\t\t\t\t\tschedule_work(&drvdata->fn_lock_sync_work);
\t\t\t\t}
\t\t\t\treturn 1;
\t\t\t}
\t\t\tbreak;""",
        text,
        "asus_event KEY_FN_ESC toggle guard",
    )

    text = replace_once(
        "\tif (usage->type == EV_KEY && value) {\n\t\tswitch (usage->code) {\n\t\tcase KEY_KBDILLUMUP:\n\t\t\treturn !asus_hid_event(ASUS_EV_BRTUP);",
        "\tif (usage->type == EV_KEY && value) {\n\t\tswitch (usage->code) {\n\t\tcase KEY_F4:\n\t\t\tif (zenbook_fn_row_policy_f4_event(hdev, usage, value))\n\t\t\t\treturn 1;\n\t\t\tbreak;\n\t\tcase KEY_KBDILLUMUP:\n\t\t\treturn !asus_hid_event(ASUS_EV_BRTUP);",
        text,
        "asus_event KEY_F4 fn backlight fallback",
    )

    text = replace_once(
        "\t\tcase 0x7e: asus_map_key_clear(KEY_EMOJI_PICKER);\tbreak;\n",
        "\t\tcase 0x7e: asus_map_key_clear(KEY_EMOJI_PICKER);\tbreak;\n"
        "\t\tcase 0x86: asus_map_key_clear(KEY_PROG1);\t\tbreak; /* MyASUS / ASUS key */\n",
        text,
        "input_mapping 0x86 MyASUS",
    )

    text = replace_once(
        "static int asus_raw_event(struct hid_device *hdev,\n"
        "\t\tstruct hid_report *report, u8 *data, int size)\n"
        "{\n"
        "\tstruct asus_drvdata *drvdata = hid_get_drvdata(hdev);\n\n"
        "\tif (drvdata->battery && data[0] == BATTERY_REPORT_ID)",
        "static int asus_raw_event(struct hid_device *hdev,\n"
        "\t\tstruct hid_report *report, u8 *data, int size)\n"
        "{\n"
        "\tstruct asus_drvdata *drvdata = hid_get_drvdata(hdev);\n"
        "\tint ret;\n\n"
        "\tret = zenbook_fn_row_policy_vendor_raw(hdev, data, size);\n"
        "\tif (ret)\n"
        "\t\treturn ret;\n\n"
        "\tret = zenbook_fn_row_policy_consumer_raw(hdev, data, size);\n"
        "\tif (ret)\n"
        "\t\treturn ret;\n\n"
        "\tret = zenbook_fn_row_policy_raw(hdev, drvdata, data, size);\n"
        "\tif (ret)\n"
        "\t\treturn ret;\n\n"
        "\tif (drvdata->battery && data[0] == BATTERY_REPORT_ID)",
        text,
        "asus_raw_event zenbook fn_row_policy",
    )

    old_fnlock = """\tif (drvdata->quirks & QUIRK_HID_FN_LOCK) {
\t\tdrvdata->fn_lock = true;
\t\tINIT_WORK(&drvdata->fn_lock_sync_work, asus_sync_fn_lock);
\t\tasus_kbd_set_fn_lock(hdev, true);
\t}

\treturn 0;
}"""

    new_fnlock = """\tif (drvdata->quirks & QUIRK_HID_FN_LOCK &&
\t\t    !drvdata->fn_lock_sync_work.func) {
\t\t/*
\t\t * UX8406 if4 uses vendor usage ranges (0x00-0xff), not individual
\t\t * input_mapping entries, so has_vendor_up may stay false even though
\t\t * fn-lock must be synced here (asus_filter_zenbook_usb_quirks limits
\t\t * QUIRK_HID_FN_LOCK to USB interface 4).
\t\t */
\t\tdrvdata->fn_lock = asus_fn_lock_default_for_device(hdev, drvdata);
\t\tINIT_WORK(&drvdata->fn_lock_sync_work, asus_sync_fn_lock);
\t\tschedule_work(&drvdata->fn_lock_sync_work);
\t}

\tif (drvdata->has_vendor_up &&
\t    (drvdata->quirks & QUIRK_USE_KBD_BACKLIGHT) &&
\t    !asus_kbd_wmi_led_control_present(hdev) &&
\t    asus_kbd_register_leds(hdev))
\t\thid_warn(hdev, "Failed to initialize backlight.\\n");

\tif (zenbook_is_duo_consumer_if3(hdev))
\t\tzenbook_duo_consumer_hdev = hdev;

\tif (zenbook_is_duo_main_keyboard(hdev, drvdata))
\t\tzenbook_duo_main_hdev = hdev;

\tif (zenbook_is_duo_vendor_if4(hdev))
\t\tzenbook_duo_vendor_hdev = hdev;

\treturn 0;
}"""

    text = replace_once(
        "static void asus_sync_fn_lock(struct work_struct *work)\n"
        "{\n"
        "\tstruct asus_drvdata *drvdata =\n"
        "\tcontainer_of(work, struct asus_drvdata, fn_lock_sync_work);\n\n"
        "\tasus_kbd_set_fn_lock(drvdata->hdev, drvdata->fn_lock);\n"
        "}",
        "static void asus_sync_fn_lock(struct work_struct *work)\n"
        "{\n"
        "\tstruct asus_drvdata *drvdata =\n"
        "\tcontainer_of(work, struct asus_drvdata, fn_lock_sync_work);\n\n"
        "\tif (drvdata->quirks & QUIRK_ZENBOOK_DUO_KEYBOARD)\n"
        "\t\tasus_kbd_init(drvdata->hdev, FEATURE_KBD_REPORT_ID);\n\n"
        "\tasus_kbd_set_fn_lock(drvdata->hdev, drvdata->fn_lock);\n"
        "}",
        text,
        "asus_sync_fn_lock zenbook handshake",
    )

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
        "\tif ((drvdata->quirks & QUIRK_HID_FN_LOCK) &&\n"
        "\t    (drvdata->quirks & QUIRK_ZENBOOK_DUO_KEYBOARD) &&\n"
        "\t    hid_is_usb(hdev) &&\n"
        "\t    to_usb_interface(hdev->dev.parent)->altsetting->desc.bInterfaceNumber == 4 &&\n"
        "\t    !drvdata->fn_lock_sync_work.func) {\n"
        "\t\tdrvdata->fn_lock = asus_fn_lock_default_for_device(hdev, drvdata);\n"
        "\t\tINIT_WORK(&drvdata->fn_lock_sync_work, asus_sync_fn_lock);\n"
        "\t\tschedule_work(&drvdata->fn_lock_sync_work);\n"
        "\t}\n\n"
        "\tif ((drvdata->quirks & QUIRK_ZENBOOK_DUO_KEYBOARD) &&\n"
        "\t    hid_is_usb(hdev) &&\n"
        "\t    to_usb_interface(hdev->dev.parent)->altsetting->desc.bInterfaceNumber == 4 &&\n"
        "\t    (drvdata->quirks & QUIRK_USE_KBD_BACKLIGHT) &&\n"
        "\t    !drvdata->kbd_backlight &&\n"
        "\t    !asus_kbd_wmi_led_control_present(hdev) &&\n"
        "\t    asus_kbd_register_leds(hdev))\n"
        "\t\thid_warn(hdev, \"Failed to initialize Zenbook Duo vendor backlight.\\n\");\n\n"
        "\tif (drvdata->quirks & (QUIRK_ROG_NKEY_KEYBOARD | QUIRK_ZENBOOK_DUO_KEYBOARD))\n\t\treturn 0;",
        text,
        "probe zenbook if4 fn_lock sync",
    )

    text = replace_once(
        "\tret = asus_hid_register_listener(&drvdata->kbd_backlight->listener);\n"
        "\tif (ret < 0) {\n"
        "\t\t/* No need to have this still around */\n"
        "\t\tdevm_kfree(&hdev->dev, drvdata->kbd_backlight);\n"
        "\t}\n\n"
        "\treturn ret;\n"
        "}",
        "\tret = asus_hid_register_listener(&drvdata->kbd_backlight->listener);\n"
        "\tif (ret < 0) {\n"
        "\t\t/* No need to have this still around */\n"
        "\t\tdevm_kfree(&hdev->dev, drvdata->kbd_backlight);\n"
        "\t} else if ((drvdata->quirks & QUIRK_ZENBOOK_DUO_KEYBOARD) &&\n"
        "\t\t   hid_is_usb(hdev) &&\n"
        "\t\t   to_usb_interface(hdev->dev.parent)->altsetting->desc.bInterfaceNumber == 4) {\n"
        "\t\tzenbook_duo_vendor_leds = drvdata->kbd_backlight;\n"
        "\t}\n\n"
        "\treturn ret;\n"
        "}",
        text,
        "zenbook_duo_vendor_leds on if4 register",
    )

    text = insert_before(
        r"/\*\n \* \[0\]       REPORT_ID \(same value defined in report descriptor\)\n",
        FN_ROW_POLICY_IMPL,
        text,
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
        "\tdrvdata->quirks = id->driver_data;\n\n\tasus_filter_zenbook_usb_quirks(hdev, drvdata);\n\n\tif (zenbook_is_duo_usb_if(hdev, 0))\n\t\tzenbook_duo_main_hdev = hdev;\n\n\tif (zenbook_is_duo_usb_if(hdev, 4))\n\t\tzenbook_duo_vendor_hdev = hdev;\n\n\t/*\n\t * T90CHI's keyboard dock",
        text,
        "zenbook probe filter and main_hdev",
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
