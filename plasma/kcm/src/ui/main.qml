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

    readonly property var tabPages: {
        var pages = [
            { title: i18n("Overview"), source: "OverviewPage.qml" },
            { title: i18n("Profiles"), source: "ProfilesPage.qml" },
            { title: i18n("Touchpad"), source: "TouchpadPage.qml" }
        ]
        if (kcm.showDisplaysTab) {
            pages.push({ title: i18n("Displays"), source: "DisplaysPage.qml" })
        }
        pages.push({ title: i18n("Sleep / Resume"), source: "SleepResumePage.qml" })
        pages.push({ title: i18n("About"), source: "AboutPage.qml" })
        return pages
    }

    ColumnLayout {
        width: root.availableWidth
        spacing: Kirigami.Units.largeSpacing

        QQC2.TabBar {
            id: tabBar
            Layout.fillWidth: true

            Repeater {
                model: root.tabPages
                QQC2.TabButton {
                    text: modelData.title
                }
            }
        }

        Loader {
            id: pageLoader
            Layout.fillWidth: true
            Layout.preferredHeight: Kirigami.Units.gridUnit * 22
            source: root.tabPages[Math.min(tabBar.currentIndex, root.tabPages.length - 1)].source
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
