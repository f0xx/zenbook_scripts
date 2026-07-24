// SPDX-License-Identifier: GPL-2.0-or-later

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts

import org.kde.kirigami as Kirigami

ColumnLayout {
    spacing: Kirigami.Units.largeSpacing

    Kirigami.Heading {
        level: 2
        text: i18n("Sleep / resume session policy")
    }

    QQC2.Label {
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        text: i18n("Per-user settings stored in %1", kcm.sessionConfigPath)
    }

    Kirigami.FormLayout {
        Layout.fillWidth: true

        QQC2.Label {
            Kirigami.FormData.label: i18n("Active profile")
            text: kcm.activeProfile
        }

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
            checked: kcm.autoReplacePlasmashell
            onToggled: kcm.autoReplacePlasmashell = checked
        }

        QQC2.SpinBox {
            Kirigami.FormData.label: i18n("QSG thread threshold")
            from: 1
            to: 256
            value: kcm.qsgThreadThreshold
            onValueModified: kcm.qsgThreadThreshold = value
        }
    }

    RowLayout {
        spacing: Kirigami.Units.largeSpacing

        QQC2.Button {
            text: i18n("Reload")
            icon.name: "document-revert"
            enabled: !kcm.busy
            onClicked: kcm.loadSession()
        }
        QQC2.Button {
            text: i18n("Save")
            icon.name: "document-save"
            enabled: kcm.sessionDirty && !kcm.busy
            onClicked: kcm.saveSession()
        }
        QQC2.Button {
            text: i18n("Reset defaults")
            enabled: !kcm.busy
            onClicked: kcm.resetSessionDefaults()
        }
    }

    QQC2.Label {
        Layout.fillWidth: true
        visible: kcm.sessionDirty
        color: Kirigami.Theme.neutralTextColor
        text: i18n("Unsaved changes")
    }
}
