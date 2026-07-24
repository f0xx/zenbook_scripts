// SPDX-License-Identifier: GPL-2.0-or-later

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts

import org.kde.kirigami as Kirigami

ColumnLayout {
    spacing: Kirigami.Units.largeSpacing

    Kirigami.Heading {
        level: 2
        text: i18n("Duo dock and displays")
    }

    QQC2.Label {
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        text: i18n("Lower panel (eDP-2) is managed by platform-duo-dock. Screen swap toggles stacked layout via platform-screen-swap.")
    }

    QQC2.TextArea {
        Layout.fillWidth: true
        Layout.preferredHeight: Kirigami.Units.gridUnit * 10
        readOnly: true
        wrapMode: TextArea.Wrap
        font.family: "monospace"
        text: kcm.duoStatusText.length > 0 ? kcm.duoStatusText : i18n("(no status yet)")
    }

    RowLayout {
        spacing: Kirigami.Units.largeSpacing

        QQC2.Button {
            text: i18n("Refresh status")
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

    QQC2.Label {
        Layout.fillWidth: true
        visible: kcm.lastCommandOutput.length > 0
        wrapMode: Text.WordWrap
        font.family: "monospace"
        text: kcm.lastCommandOutput
    }
}
