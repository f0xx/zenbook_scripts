#!/usr/bin/env python3
"""Optional KDE/Qt GUI configurator. Requires PySide6."""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QApplication,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QSlider,
        QSpinBox,
        QWidget,
    )
except ImportError:
    print("PySide6 is not installed. Use configure.py or configure.sh instead.", file=sys.stderr)
    raise SystemExit(1)

from configure import DEFAULT_CONFIG, write_config
import configparser
import subprocess


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Zenbook Duo Keyboard")
        self.cfg = configparser.ConfigParser()
        if DEFAULT_CONFIG.exists():
            self.cfg.read(DEFAULT_CONFIG)
        self.cfg.setdefault("keyboard", {})
        self.cfg.setdefault("duo", {})

        root = QWidget()
        self.setCentralWidget(root)
        form = QFormLayout(root)

        kb = self.cfg["keyboard"]
        self.usb_vendor = QSpinBox()
        self.usb_vendor.setRange(0, 0xFFFF)
        self.usb_vendor.setDisplayIntegerBase(16)
        self.usb_vendor.setPrefix("0x")
        self.usb_vendor.setValue(int(kb.get("usb_vendor_id", "0b05"), 16))
        form.addRow("USB vendor", self.usb_vendor)

        self.usb_product = QSpinBox()
        self.usb_product.setRange(0, 0xFFFF)
        self.usb_product.setDisplayIntegerBase(16)
        self.usb_product.setPrefix("0x")
        self.usb_product.setValue(int(kb.get("usb_product_id", "1b2c"), 16))
        form.addRow("USB product", self.usb_product)

        self.bt_product = QSpinBox()
        self.bt_product.setRange(0, 0xFFFF)
        self.bt_product.setDisplayIntegerBase(16)
        self.bt_product.setPrefix("0x")
        self.bt_product.setValue(int(kb.get("bt_product_id", "1b2d"), 16))
        form.addRow("BT product", self.bt_product)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 3)
        self.slider.setValue(int(kb.get("default_brightness", "1")))
        form.addRow("Brightness", self.slider)

        buttons = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save)
        test_btn = QPushButton("Apply")
        test_btn.clicked.connect(self.apply_brightness)
        buttons.addWidget(save_btn)
        buttons.addWidget(test_btn)
        form.addRow(buttons)

        form.addRow(QLabel(f"Config: {DEFAULT_CONFIG}"))

    def save(self) -> None:
        kb = self.cfg["keyboard"]
        kb["usb_vendor_id"] = f"{self.usb_vendor.value():04x}"
        kb["usb_product_id"] = f"{self.usb_product.value():04x}"
        kb["bt_vendor_id"] = "0b05"
        kb["bt_product_id"] = f"{self.bt_product.value():04x}"
        kb["usb_windex"] = kb.get("usb_windex", "4")
        kb["default_brightness"] = str(self.slider.value())
        self.cfg["duo"]["default_backlight"] = kb["default_brightness"]
        write_config(self.cfg, DEFAULT_CONFIG)
        QMessageBox.information(self, "Saved", f"Wrote {DEFAULT_CONFIG}")

    def apply_brightness(self) -> None:
        script = Path(__file__).resolve().parent / "brightness.py"
        level = self.slider.value()
        subprocess.run(
            [
                sys.executable,
                str(script),
                str(level),
                "--vendor-id",
                f"0x{self.usb_vendor.value():04x}",
                "--product-id",
                f"0x{self.usb_product.value():04x}",
                "--bt-product-id",
                f"0x{self.bt_product.value():04x}",
            ],
            check=False,
        )


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
