// SPDX-License-Identifier: GPL-2.0-or-later

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts

import org.kde.kirigami as Kirigami

ColumnLayout {
    spacing: Kirigami.Units.largeSpacing

    Kirigami.Heading {
        level: 2
        text: i18n("Platform probe")
    }

    QQC2.Label {
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        text: i18n("Summary from platform-probe (read-only). Use Refresh after changing hardware or kernel features.")
    }

    QQC2.TextArea {
        Layout.fillWidth: true
        Layout.preferredHeight: Kirigami.Units.gridUnit * 16
        readOnly: true
        wrapMode: TextArea.Wrap
        font.family: "monospace"
        text: kcm.probeText.length > 0 ? kcm.probeText : i18n("(no output yet)")
    }

    RowLayout {
        QQC2.Button {
            text: i18n("Refresh")
            icon.name: "view-refresh"
            enabled: !kcm.busy
            onClicked: kcm.refreshProbe()
        }
    }
}
