// SPDX-License-Identifier: GPL-2.0-or-later

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts

import org.kde.kirigami as Kirigami

ColumnLayout {
    id: root
    width: parent ? parent.width : implicitWidth
    spacing: Kirigami.Units.largeSpacing

    property var knobs: ({})
    readonly property bool softAccelOn: knobs.soft_accel_enabled === true
    readonly property bool liveRunning: (kcm.touchpadStatusText || "").indexOf("live:     running") >= 0
        || (kcm.touchpadStatusText || "").indexOf("live:\trunning") >= 0

    function reload(refreshStatus) {
        kcm.loadTouchpadKnobs()
        if (refreshStatus !== false) {
            kcm.refreshTouchpadStatus()
        }
        try {
            knobs = JSON.parse(kcm.touchpadKnobsJson)
        } catch (e) {
            knobs = {}
        }
    }

    function patch(field, value) {
        var next = JSON.parse(JSON.stringify(knobs))
        next[field] = value
        knobs = next
        kcm.touchpadKnobsJson = JSON.stringify(next, null, 2)
    }

    Component.onCompleted: reload(false)
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
        QQC2.ComboBox {
            Kirigami.FormData.label: i18n("Filter profile")
            model: [
                { text: i18n("Default (outlier reject)"), value: "default" },
                { text: i18n("Adaptive (learn matrix)"), value: "adaptive" }
            ]
            textRole: "text"
            currentIndex: {
                var p = knobs.filter_profile || "default"
                return p === "adaptive" ? 1 : 0
            }
            onActivated: root.patch("filter_profile", model[currentIndex].value)
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
            enabled: (knobs.filter_profile || "default") !== "adaptive"
            checked: knobs.outlier_enabled !== false
            onToggled: root.patch("outlier_enabled", checked)
        }
        QQC2.SpinBox {
            Kirigami.FormData.label: i18n("Max delta")
            enabled: (knobs.filter_profile || "default") !== "adaptive"
            from: 50; to: 5000; stepSize: 50
            value: knobs.max_delta || 1200
            onValueModified: root.patch("max_delta", value)
        }
        QQC2.CheckBox {
            Kirigami.FormData.label: i18n("Soft accel")
            checked: root.softAccelOn
            onToggled: root.patch("soft_accel_enabled", checked)
        }
        QQC2.SpinBox {
            Kirigami.FormData.label: i18n("Soft gain (×100)")
            enabled: root.softAccelOn
            from: 50; to: 300
            value: Math.round((knobs.soft_accel_gain || 1.6) * 100)
            onValueModified: root.patch("soft_accel_gain", value / 100.0)
        }
        QQC2.ComboBox {
            Kirigami.FormData.label: i18n("Soft accel curve")
            enabled: root.softAccelOn
            model: [
                { text: i18n("Linear (constant gain)"), value: "linear" },
                { text: i18n("Non-linear (slow moves ~1×)"), value: "nonlinear" }
            ]
            textRole: "text"
            currentIndex: {
                var m = knobs.soft_accel_mode || "linear"
                return m === "nonlinear" ? 1 : 0
            }
            onActivated: root.patch("soft_accel_mode", model[currentIndex].value)
        }
    }

    Kirigami.InlineMessage {
        Layout.fillWidth: true
        visible: kcm.lastError.length > 0
        type: Kirigami.MessageType.Error
        text: kcm.lastError
    }

    RowLayout {
        QQC2.Button {
            text: liveRunning ? i18n("Stop live filter") : i18n("Start live filter")
            icon.name: liveRunning ? "media-playback-stop" : "media-playback-start"
            onClicked: liveRunning ? kcm.stopTouchpadLiveFilter() : kcm.startTouchpadLiveFilter()
        }
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
        wrapMode: Text.WordWrap
        visible: (knobs.filter_profile || "default") === "adaptive"
        text: i18n("Adaptive profile: outlier reject is replaced by the learn matrix (typing-gated). Soft accel still runs on every motion frame after the matrix — enable it and Apply, then restart the live filter.")
        opacity: 0.85
    }

    QQC2.Label {
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        text: i18n("Apply saves touchpad.json. Restart the live filter after knob changes (Start/Stop above). Soft accel only affects the live uinput path, not raw libinput in the DE.")
        opacity: 0.75
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
            text: kcm.touchpadStatusText || i18n("(loading…)")
            font.family: "monospace"
        }
    }

    Kirigami.InlineMessage {
        Layout.fillWidth: true
        type: Kirigami.MessageType.Information
        text: i18n("Planned: live event sparkline (ΔX/ΔY over time) in this tab — use the full tuner monitor until then.")
        visible: true
    }
}
