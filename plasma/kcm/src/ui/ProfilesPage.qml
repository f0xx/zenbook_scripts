// SPDX-License-Identifier: GPL-2.0-or-later

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts

import org.kde.kirigami as Kirigami

ScrollView {
    id: root
    clip: true

    property var doc: ({})
    property int modeIndex: 0
    readonly property var modeNames: ["auto", "quiet", "balanced", "performance", "night"]
    readonly property string modeName: modeNames[Math.min(modeIndex, modeNames.length - 1)]

    function reload() {
        try {
            doc = JSON.parse(kcm.profilesJson)
        } catch (e) {
            doc = {}
        }
    }

    function commit() {
        kcm.profilesJson = JSON.stringify(doc, null, 2)
    }

    function ensureMode(name) {
        if (!doc.modes)
            doc.modes = {}
        if (!doc.modes[name])
            doc.modes[name] = {}
        return doc.modes[name]
    }

    Component.onCompleted: reload()
    Connections {
        target: kcm
        function onProfilesChanged() { root.reload() }
    }

    ColumnLayout {
        width: root.availableWidth
        spacing: Kirigami.Units.largeSpacing

        Kirigami.Heading {
            level: 2
            text: i18n("Power & thermal profiles")
        }

        QQC2.Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: i18n("Stored in %1. Auto uses fan-control.json rules; other modes can use schedules and triggers (evaluator coming in daemon).", kcm.profilesConfigPath)
        }

        Kirigami.FormLayout {
            Layout.fillWidth: true

            QQC2.ComboBox {
                Kirigami.FormData.label: i18n("Active mode")
                model: [
                    i18n("Auto (adaptive)"),
                    i18n("Quiet (powersave)"),
                    i18n("Balanced"),
                    i18n("Performance"),
                    i18n("Night")
                ]
                currentIndex: {
                    var m = doc.active_mode || "auto"
                    var i = modeNames.indexOf(m)
                    return i >= 0 ? i : 0
                }
                onActivated: {
                    doc.active_mode = modeNames[currentIndex]
                    commit()
                }
            }

            QQC2.CheckBox {
                Kirigami.FormData.label: i18n("Desktop notifications")
                checked: doc.notifications ? doc.notifications.enabled !== false : true
                onToggled: {
                    if (!doc.notifications) doc.notifications = {}
                    doc.notifications.enabled = checked
                    if (doc.notifications.on_mode_switch === undefined)
                        doc.notifications.on_mode_switch = true
                    commit()
                }
            }

            QQC2.CheckBox {
                Kirigami.FormData.label: i18n("Notify on mode switch")
                checked: doc.notifications ? doc.notifications.on_mode_switch !== false : true
                onToggled: {
                    if (!doc.notifications) doc.notifications = {}
                    doc.notifications.on_mode_switch = checked
                    commit()
                }
            }
        }

        QQC2.TabBar {
            id: modeBar
            Layout.fillWidth: true
            currentIndex: root.modeIndex
            onCurrentIndexChanged: root.modeIndex = currentIndex
            Repeater {
                model: [i18n("Auto"), i18n("Quiet"), i18n("Balanced"), i18n("Performance"), i18n("Night")]
                QQC2.TabButton { text: modelData }
            }
        }

        Kirigami.FormLayout {
            Layout.fillWidth: true
            visible: modeName === "auto"

            QQC2.Label {
                Kirigami.FormData.label: i18n("Description")
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
                text: ensureMode("auto").description || i18n("Adaptive rules from platform-fan-control. View-only — use tray or set Active mode to Auto.")
            }
        }

        Kirigami.FormLayout {
            Layout.fillWidth: true
            visible: modeName === "quiet" || modeName === "balanced" || modeName === "performance"

            QQC2.CheckBox {
                id: schedEn
                Kirigami.FormData.label: i18n("Schedule")
                checked: {
                    var m = ensureMode(modeName).schedule
                    return m && m.enabled
                }
                onToggled: {
                    var m = ensureMode(modeName)
                    if (!m.schedule) m.schedule = {}
                    m.schedule.enabled = checked
                    commit()
                }
            }
            QQC2.TextField {
                Kirigami.FormData.label: i18n("Start (HH:MM)")
                enabled: schedEn.checked
                text: (ensureMode(modeName).schedule || {}).start || "22:00"
                onEditingFinished: {
                    ensureMode(modeName).schedule.start = text
                    commit()
                }
            }
            QQC2.TextField {
                Kirigami.FormData.label: i18n("Stop (HH:MM)")
                enabled: schedEn.checked
                text: (ensureMode(modeName).schedule || {}).stop || "07:00"
                onEditingFinished: {
                    ensureMode(modeName).schedule.stop = text
                    commit()
                }
            }
            QQC2.CheckBox {
                Kirigami.FormData.label: i18n("Low CPU trigger")
                checked: {
                    var t = (ensureMode(modeName).triggers || {}).low_cpu
                    return t && t.enabled
                }
                onToggled: {
                    var m = ensureMode(modeName)
                    if (!m.triggers) m.triggers = {}
                    if (!m.triggers.low_cpu) m.triggers.low_cpu = {}
                    m.triggers.low_cpu.enabled = checked
                    commit()
                }
            }
            QQC2.SpinBox {
                Kirigami.FormData.label: i18n("Load below (%)")
                from: 1; to: 100
                value: ((ensureMode(modeName).triggers || {}).low_cpu || {}).load_pct_max || 20
                onValueModified: {
                    ensureMode(modeName).triggers.low_cpu.load_pct_max = value
                    commit()
                }
            }
            QQC2.SpinBox {
                Kirigami.FormData.label: i18n("For (minutes)")
                from: 1; to: 120
                value: ((ensureMode(modeName).triggers || {}).low_cpu || {}).duration_min || 3
                onValueModified: {
                    ensureMode(modeName).triggers.low_cpu.duration_min = value
                    commit()
                }
            }
            QQC2.CheckBox {
                Kirigami.FormData.label: i18n("Only on battery")
                checked: ((ensureMode(modeName).triggers || {}).low_cpu || {}).require_battery !== false
                onToggled: {
                    ensureMode(modeName).triggers.low_cpu.require_battery = checked
                    commit()
                }
            }
            QQC2.CheckBox {
                Kirigami.FormData.label: i18n("Battery timeout trigger")
                checked: {
                    var t = (ensureMode(modeName).triggers || {}).battery_timeout
                    return t && t.enabled
                }
                onToggled: {
                    var m = ensureMode(modeName)
                    if (!m.triggers) m.triggers = {}
                    if (!m.triggers.battery_timeout) m.triggers.battery_timeout = {}
                    m.triggers.battery_timeout.enabled = checked
                    commit()
                }
            }
            QQC2.SpinBox {
                Kirigami.FormData.label: i18n("Within (minutes)")
                from: 5; to: 240
                value: ((ensureMode(modeName).triggers || {}).battery_timeout || {}).minutes || 30
                onValueModified: {
                    ensureMode(modeName).triggers.battery_timeout.minutes = value
                    commit()
                }
            }
        }

        Kirigami.FormLayout {
            Layout.fillWidth: true
            visible: modeName === "night"

            QQC2.CheckBox {
                Kirigami.FormData.label: i18n("Night mode enabled")
                checked: ensureMode("night").enabled === true
                onToggled: {
                    ensureMode("night").enabled = checked
                    commit()
                }
            }
            QQC2.ComboBox {
                Kirigami.FormData.label: i18n("Thermal base")
                model: [i18n("Auto"), i18n("Quiet"), i18n("Balanced"), i18n("Performance")]
                currentIndex: {
                    var b = ensureMode("night").base_mode || "quiet"
                    return ["auto", "quiet", "balanced", "performance"].indexOf(b)
                }
                onActivated: {
                    ensureMode("night").base_mode = ["auto", "quiet", "balanced", "performance"][currentIndex]
                    commit()
                }
            }
            QQC2.CheckBox {
                Kirigami.FormData.label: i18n("Schedule")
                checked: (ensureMode("night").schedule || {}).enabled !== false
                onToggled: {
                    if (!ensureMode("night").schedule) ensureMode("night").schedule = {}
                    ensureMode("night").schedule.enabled = checked
                    commit()
                }
            }
            QQC2.TextField {
                Kirigami.FormData.label: i18n("Start")
                text: (ensureMode("night").schedule || {}).start || "23:00"
                onEditingFinished: { ensureMode("night").schedule.start = text; commit() }
            }
            QQC2.TextField {
                Kirigami.FormData.label: i18n("Stop")
                text: (ensureMode("night").schedule || {}).stop || "06:00"
                onEditingFinished: { ensureMode("night").schedule.stop = text; commit() }
            }
            QQC2.CheckBox {
                Kirigami.FormData.label: i18n("Turn screen off")
                checked: (ensureMode("night").screen || {}).power_off !== false
                onToggled: {
                    if (!ensureMode("night").screen) ensureMode("night").screen = {}
                    ensureMode("night").screen.power_off = checked
                    commit()
                }
            }
            QQC2.SpinBox {
                Kirigami.FormData.label: i18n("Screen brightness")
                from: 0; to: 100
                value: (ensureMode("night").screen || {}).brightness || 0
                onValueModified: {
                    if (!ensureMode("night").screen) ensureMode("night").screen = {}
                    ensureMode("night").screen.brightness = value
                    commit()
                }
            }
            QQC2.CheckBox {
                Kirigami.FormData.label: i18n("Keyboard backlight")
                checked: (ensureMode("night").keyboard_backlight || {}).enabled === true
                onToggled: {
                    if (!ensureMode("night").keyboard_backlight) ensureMode("night").keyboard_backlight = {}
                    ensureMode("night").keyboard_backlight.enabled = checked
                    commit()
                }
            }
            QQC2.SpinBox {
                Kirigami.FormData.label: i18n("Keyboard level")
                from: 0; to: 3
                value: (ensureMode("night").keyboard_backlight || {}).level || 0
                onValueModified: {
                    if (!ensureMode("night").keyboard_backlight) ensureMode("night").keyboard_backlight = {}
                    ensureMode("night").keyboard_backlight.level = value
                    commit()
                }
            }
            QQC2.CheckBox {
                Kirigami.FormData.label: i18n("Keep networking up")
                checked: (ensureMode("night").network || {}).stay_up !== false
                onToggled: {
                    if (!ensureMode("night").network) ensureMode("night").network = {}
                    ensureMode("night").network.stay_up = checked
                    commit()
                }
            }
            QQC2.Label {
                Kirigami.FormData.label: i18n("Note")
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
                text: ensureMode("night").notes || i18n("Scheduled night applies when the laptop is awake and the lid is open. Closed lid or hibernate requires platform-night-mode + elogind setup.")
            }
        }

        RowLayout {
            spacing: Kirigami.Units.largeSpacing
            QQC2.Button {
                text: i18n("Reload")
                icon.name: "document-revert"
                onClicked: { kcm.loadProfiles(); reload() }
            }
            QQC2.Button {
                text: i18n("Save")
                icon.name: "document-save"
                enabled: kcm.profilesDirty
                onClicked: kcm.saveProfiles()
            }
            QQC2.Button {
                text: i18n("Reset all defaults")
                onClicked: { kcm.resetProfilesDefaults(); reload() }
            }
            QQC2.Button {
                text: i18n("Apply active mode")
                icon.name: "system-run"
                enabled: !kcm.busy
                onClicked: kcm.applyActiveProfile()
            }
        }

        QQC2.Label {
            visible: kcm.profilesDirty
            color: Kirigami.Theme.neutralTextColor
            text: i18n("Unsaved profile changes")
        }
    }
}
