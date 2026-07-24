// SPDX-License-Identifier: GPL-2.0-or-later

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts

import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCMUtils

KCMUtils.ScrollViewKCM {
    id: root

    implicitWidth: Kirigami.Units.gridUnit * 44
    implicitHeight: Kirigami.Units.gridUnit * 30

    ColumnLayout {
        width: root.availableWidth
        spacing: Kirigami.Units.largeSpacing

        QQC2.TabBar {
            id: tabBar
            Layout.fillWidth: true

            QQC2.TabButton { text: i18n("Overview") }
            QQC2.TabButton { text: i18n("Duo / Displays") }
            QQC2.TabButton { text: i18n("Sleep / Resume") }
            QQC2.TabButton { text: i18n("About") }
        }

        Loader {
            id: pageLoader
            Layout.fillWidth: true
            Layout.preferredHeight: Kirigami.Units.gridUnit * 22
            source: [
                "OverviewPage.qml",
                "DuoDisplaysPage.qml",
                "SleepResumePage.qml",
                "AboutPage.qml"
            ][tabBar.currentIndex]
        }

        QQC2.Label {
            Layout.fillWidth: true
            visible: kcm.lastError.length > 0
            color: Kirigami.Theme.negativeTextColor
            wrapMode: Text.WordWrap
            text: kcm.lastError
        }

        QQC2.BusyIndicator {
            Layout.alignment: Qt.AlignHCenter
            running: kcm.busy
            visible: kcm.busy
        }
    }
}
