// SPDX-License-Identifier: GPL-2.0-or-later

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts

import org.kde.kirigami as Kirigami

ColumnLayout {
    spacing: Kirigami.Units.largeSpacing

    Kirigami.Heading {
        level: 2
        text: i18n("About")
    }

    Kirigami.FormLayout {
        Layout.fillWidth: true

        QQC2.Label {
            Kirigami.FormData.label: i18n("Module version")
            text: kcm.version
        }

        Kirigami.UrlButton {
            Kirigami.FormData.label: i18n("Documentation")
            url: kcm.documentationUrl
            text: i18n("README.plasma.md on GitHub")
        }
    }

    QQC2.Label {
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        text: i18n("zenbook_scripts Plasma integration (KCModule MVP). Architecture, session policy, and roadmap are in the linked README.")
    }

    QQC2.Label {
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        text: i18n("Open this module standalone: kcmshell6 kcm_zenbook_platform")
    }
}
