// SPDX-License-Identifier: GPL-2.0-or-later

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts

import org.kde.kirigami as Kirigami

ColumnLayout {
    width: parent ? parent.width : implicitWidth
    spacing: Kirigami.Units.largeSpacing

    Component.onCompleted: {
        if (kcm.hasDuoDock && kcm.duoStatusText.length === 0) {
            kcm.refreshDuoStatus()
        }
        if (kcm.hasScreenpad && kcm.screenpadStatusText.length === 0) {
            kcm.refreshScreenpadStatus()
        }
    }

    Kirigami.Heading {
        level: 2
        text: i18n("Displays")
    }

    QQC2.Label {
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        text: i18n("Detected: %1 — Duo dock: %2, ScreenPad: %3",
                   kcm.dmiProduct,
                   kcm.hasDuoDock ? i18n("yes") : i18n("no"),
                   kcm.hasScreenpad ? i18n("yes") : i18n("no"))
    }

    // --- Duo dual-eDP (UX8406 / UX581 / …) ---
    ColumnLayout {
        visible: kcm.hasDuoDock
        spacing: Kirigami.Units.smallSpacing
        Layout.fillWidth: true

        Kirigami.Heading {
            level: 3
            text: i18n("Duo dock (lower eDP)")
        }

        QQC2.Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: i18n("Lower panel is managed by platform-duo-dock. Screen swap toggles stacked layout via platform-screen-swap.")
        }

        QQC2.TextArea {
            Layout.fillWidth: true
            Layout.preferredHeight: Kirigami.Units.gridUnit * 8
            readOnly: true
            wrapMode: TextEdit.Wrap
            font.family: "monospace"
            text: kcm.duoStatusText.length > 0 ? kcm.duoStatusText : i18n("(no status yet)")
        }

        RowLayout {
            spacing: Kirigami.Units.largeSpacing

            QQC2.Button {
                text: i18n("Refresh")
                icon.name: "view-refresh"
                enabled: !kcm.busy
                onClicked: kcm.refreshDuoStatus()
            }
            QQC2.Button {
                text: i18n("Docked")
                icon.name: "link"
                enabled: !kcm.busy
                onClicked: kcm.runDuoDocked()
            }
            QQC2.Button {
                text: i18n("Undocked")
                icon.name: "link-broken"
                enabled: !kcm.busy
                onClicked: kcm.runDuoUndocked()
            }
            QQC2.Button {
                text: i18n("Screen swap")
                icon.name: "view-split-top-bottom"
                enabled: !kcm.busy
                onClicked: kcm.runScreenSwap()
            }
        }
    }

    // --- ScreenPad (UX5400 and similar) ---
    ColumnLayout {
        visible: kcm.hasScreenpad
        spacing: Kirigami.Units.smallSpacing
        Layout.fillWidth: true

        Kirigami.Heading {
            level: 3
            text: i18n("ScreenPad")
        }

        QQC2.Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: i18n("Secondary panel backlight via asus_screenpad sysfs (screenpad CLI). Not the same as Duo eDP-2 dock.")
        }

        QQC2.TextArea {
            Layout.fillWidth: true
            Layout.preferredHeight: Kirigami.Units.gridUnit * 6
            readOnly: true
            wrapMode: TextEdit.Wrap
            font.family: "monospace"
            text: kcm.screenpadStatusText.length > 0 ? kcm.screenpadStatusText : i18n("(no status yet)")
        }

        RowLayout {
            spacing: Kirigami.Units.largeSpacing

            QQC2.Button {
                text: i18n("Refresh")
                icon.name: "view-refresh"
                enabled: !kcm.busy
                onClicked: kcm.refreshScreenpadStatus()
            }
            QQC2.Button {
                text: i18n("On")
                icon.name: "video-display"
                enabled: !kcm.busy
                onClicked: kcm.runScreenpadOn()
            }
            QQC2.Button {
                text: i18n("Off")
                icon.name: "video-display-symbolic"
                enabled: !kcm.busy
                onClicked: kcm.runScreenpadOff()
            }
            QQC2.Button {
                text: i18n("Sync to main")
                icon.name: "object-linked"
                enabled: !kcm.busy
                onClicked: kcm.runScreenpadSync()
            }
        }
    }

    QQC2.Label {
        Layout.fillWidth: true
        visible: kcm.lastCommandOutput.length > 0
        wrapMode: Text.WordWrap
        font.family: "monospace"
        text: kcm.lastCommandOutput
    }
}
