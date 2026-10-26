// SPDX-License-Identifier: GPL-2.0-or-later

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts

import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCMUtils

KCMUtils.SimpleKCM {
    id: root

    implicitWidth: Kirigami.Units.gridUnit * 44

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

    function activePageHeight() {
        var loader = stack.children[stack.currentIndex]
        if (!loader || !loader.item)
            return Kirigami.Units.gridUnit * 28
        var h = loader.item.implicitHeight
        if (h > 0)
            return h
        if (loader.item.childrenRect)
            return loader.item.childrenRect.height + Kirigami.Units.gridUnit * 2
        return Kirigami.Units.gridUnit * 28
    }

    ColumnLayout {
        width: parent.width
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

        StackLayout {
            id: stack
            Layout.fillWidth: true
            currentIndex: tabBar.currentIndex
            Layout.preferredHeight: root.activePageHeight()

            Repeater {
                model: root.tabPages

                Loader {
                    Layout.fillWidth: true
                    active: true
                    source: modelData.source
                    onLoaded: {
                        if (item && item.width !== undefined) {
                            item.width = Qt.binding(function() { return stack.width })
                        }
                        stack.Layout.preferredHeight = Qt.binding(function() { return root.activePageHeight() })
                    }
                    onStatusChanged: {
                        if (status === Loader.Error)
                            console.warn("KCM page failed:", source, sourceComponent ? sourceComponent.errorString() : "")
                    }
                }
            }
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
