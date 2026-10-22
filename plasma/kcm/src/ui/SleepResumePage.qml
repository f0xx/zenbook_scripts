// SPDX-License-Identifier: GPL-2.0-or-later

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts

import org.kde.kirigami as Kirigami

ColumnLayout {
    width: parent ? parent.width : implicitWidth
    spacing: Kirigami.Units.largeSpacing

    Kirigami.Heading {
        level: 2
        text: i18n("Sleep / resume session policy")
    }

    QQC2.Label {
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        text: i18n("Per-user settings in %1, applied by platform-session on sleep/resume (elogind hook).", kcm.sessionConfigPath)
    }

    Kirigami.Heading {
        level: 3
        text: i18n("Resume / sleep hooks")
    }

    Kirigami.FormLayout {
        Layout.fillWidth: true
        Layout.alignment: Qt.AlignTop

        QQC2.Label {
            Kirigami.FormData.label: i18n("Active profile")
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
            text: kcm.activeProfile
        }

        QQC2.Label {
            Kirigami.FormData.label: i18n("Hook lists")
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
            font.family: "monospace"
            text: kcm.sessionHooksSummary.length > 0
                ? kcm.sessionHooksSummary
                : i18n("(default hooks — edit session.json for custom lists)")
        }

        QQC2.Label {
            Kirigami.FormData.label: i18n(" ")
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
            opacity: 0.8
            text: i18n("Typical on_resume: brightness_restore, fan_sleep_post, touchpad_reassert, touch_map_apply. Hook lists are preserved when you save plasmashell options below.")
        }
    }

    Kirigami.Heading {
        level: 3
        text: i18n("Plasma shell (post-resume)")
    }

    Kirigami.FormLayout {
        Layout.fillWidth: true
        Layout.alignment: Qt.AlignTop

        QQC2.CheckBox {
            Kirigami.FormData.label: i18n("Restore presentation after plasmashell replace")
            checked: kcm.restoreAfterPlasmashellReplace
            onToggled: kcm.restoreAfterPlasmashellReplace = checked
        }

        QQC2.CheckBox {
            Kirigami.FormData.label: i18n("Watch QSG render threads")
            checked: kcm.watchQsgThreads
            onToggled: kcm.watchQsgThreads = checked
        }

        QQC2.CheckBox {
            Kirigami.FormData.label: i18n("Auto plasmashell --replace")
            enabled: kcm.watchQsgThreads
            checked: kcm.autoReplacePlasmashell
            onToggled: kcm.autoReplacePlasmashell = checked
        }

        QQC2.SpinBox {
            Kirigami.FormData.label: i18n("QSG thread threshold")
            enabled: kcm.watchQsgThreads
            from: 1
            to: 256
            value: kcm.qsgThreadThreshold
            onValueModified: kcm.qsgThreadThreshold = value
        }
    }
}
