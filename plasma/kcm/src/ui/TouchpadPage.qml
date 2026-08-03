// SPDX-License-Identifier: GPL-2.0-or-later

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts

import org.kde.kirigami as Kirigami

ColumnLayout {
    id: root
    spacing: Kirigami.Units.largeSpacing

    property var knobs: ({})

    function reload() {
        kcm.loadTouchpadKnobs()
        try {
            knobs = JSON.parse(kcm.touchpadKnobsJson)
        } catch (e) {
            knobs = {}
        }
    }

    function patch(field, value) {
        knobs[field] = value
        kcm.touchpadKnobsJson = JSON.stringify(knobs, null, 2)
    }

    Component.onCompleted: reload()
    Connections {
        target: kcm
        function onTouchpadKnobsChanged() {
            try {
                knobs = JSON.parse(kcm.touchpadKnobsJson)
            } catch (e) {
                knobs = {}
            }
        }
    }

    Kirigami.Heading {
        level: 2
        text: i18n("Touchpad live filter")
    }

    QQC2.Label {
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        text: knobs.device_name
            ? i18n("Device: %1 (%2)", knobs.device_name, knobs.device_key)
            : i18n("No touchpad detected")
    }

    Kirigami.FormLayout {
        Layout.fillWidth: true

        QQC2.CheckBox {
            Kirigami.FormData.label: i18n("Profile enabled")
            checked: knobs.profile_enabled === true
            onToggled: root.patch("profile_enabled", checked)
        }
        QQC2.CheckBox {
            Kirigami.FormData.label: i18n("Typing inhibit")
            checked: knobs.typing_enabled !== false
            onToggled: root.patch("typing_enabled", checked)
        }
        QQC2.SpinBox {
            Kirigami.FormData.label: i18n("Typing window (ms)")
            from: 50; to: 2000; stepSize: 50
            value: knobs.typing_window_ms || 350
            onValueModified: root.patch("typing_window_ms", value)
        }
        QQC2.CheckBox {
            Kirigami.FormData.label: i18n("Exec delay")
            checked: knobs.delay_enabled !== false
            onToggled: root.patch("delay_enabled", checked)
        }
        QQC2.SpinBox {
            Kirigami.FormData.label: i18n("Delay (ms)")
            from: 0; to: 200
            value: knobs.delay_ms || 25
            onValueModified: root.patch("delay_ms", value)
        }
        QQC2.CheckBox {
            Kirigami.FormData.label: i18n("Outlier reject")
            checked: knobs.outlier_enabled !== false
            onToggled: root.patch("outlier_enabled", checked)
        }
        QQC2.SpinBox {
            Kirigami.FormData.label: i18n("Max delta")
            from: 50; to: 5000; stepSize: 50
            value: knobs.max_delta || 1200
            onValueModified: root.patch("max_delta", value)
        }
        QQC2.CheckBox {
            Kirigami.FormData.label: i18n("Soft accel")
            checked: knobs.soft_accel_enabled === true
            onToggled: root.patch("soft_accel_enabled", checked)
        }
        QQC2.SpinBox {
            Kirigami.FormData.label: i18n("Soft gain (×100)")
            from: 50; to: 300
            value: Math.round((knobs.soft_accel_gain || 1.6) * 100)
            onValueModified: root.patch("soft_accel_gain", value / 100.0)
        }
    }

    RowLayout {
        QQC2.Button {
            text: i18n("Open full tuner…")
            icon.name: "input-touchpad"
            onClicked: kcm.openTouchpadTuner()
        }
        QQC2.Button {
            text: i18n("Reload")
            onClicked: root.reload()
        }
    }

    QQC2.Label {
        Layout.fillWidth: true
        text: i18n("Live status")
        font.bold: true
    }
    QQC2.ScrollView {
        Layout.fillWidth: true
        Layout.preferredHeight: Kirigami.Units.gridUnit * 8
        clip: true
        QQC2.TextArea {
            readOnly: true
            text: kcm.touchpadStatusText || ""
            font.family: "monospace"
        }
    }
}
