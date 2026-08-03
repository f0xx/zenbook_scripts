// SPDX-License-Identifier: GPL-2.0-or-later

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts

import org.kde.kirigami as Kirigami

ColumnLayout {
    spacing: Kirigami.Units.largeSpacing

    Kirigami.Heading {
        level: 2
        text: i18n("Touchpad live filter")
    }

    QQC2.Label {
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        text: i18n("Same settings as platform-touchpad-gui: per-device typing inhibit, exec_delay, outlier_reject, soft_accel, and live filter on/off. Use the tuner for full knob control and calibrate.")
    }

    RowLayout {
        spacing: Kirigami.Units.largeSpacing
        QQC2.Button {
            text: i18n("Open touchpad tuner…")
            icon.name: "input-touchpad"
            onClicked: kcm.openTouchpadTuner()
        }
        QQC2.Button {
            text: i18n("Refresh status")
            icon.name: "view-refresh"
            enabled: !kcm.busy
            onClicked: kcm.refreshTouchpadStatus()
        }
    }

    QQC2.Label {
        Layout.fillWidth: true
        text: i18n("Live filter status")
        font.bold: true
    }

    QQC2.ScrollView {
        Layout.fillWidth: true
        Layout.preferredHeight: Kirigami.Units.gridUnit * 14
        clip: true
        QQC2.TextArea {
            readOnly: true
            text: kcm.touchpadStatusText || i18n("(no data — install platform-touchpad)")
            font.family: "monospace"
            wrapMode: Text.NoWrap
        }
    }

    Component.onCompleted: kcm.refreshTouchpadStatus()
}
