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
            Kirigami.FormData.helpText: i18n("Re-apply PowerDevil presentation mode after a plasmashell --replace (that mode is owned by plasmashell and is lost on replace).")
            checked: kcm.restoreAfterPlasmashellReplace
            onToggled: kcm.restoreAfterPlasmashellReplace = checked
        }

        QQC2.CheckBox {
            Kirigami.FormData.label: i18n("Watch QSG render threads")
            Kirigami.FormData.helpText: i18n("After resume, count plasmashell threads whose names match QSGRenderThread / Mesa (gdrv, traceq). Useful on Plasma 6.6 Wayland when resume leaks render threads (common on dual-eDP Duo). Off by default.")
            checked: kcm.watchQsgThreads
            onToggled: kcm.watchQsgThreads = checked
        }

        QQC2.CheckBox {
            Kirigami.FormData.label: i18n("Auto plasmashell --replace")
            Kirigami.FormData.helpText: i18n("When watch is on and the thread count exceeds the threshold, run plasmashell --replace (does not kill apps; kwin_wayland keeps windows). Presentation mode is still lost unless restore above is enabled.")
            enabled: kcm.watchQsgThreads
            checked: kcm.autoReplacePlasmashell
            onToggled: kcm.autoReplacePlasmashell = checked
        }

        QQC2.SpinBox {
            Kirigami.FormData.label: i18n("QSG thread threshold")
            Kirigami.FormData.helpText: i18n("Total QSG/Mesa-related threads across all plasmashell PIDs before auto-replace fires. Typical healthy: under ~16; leaked resume state on UX581/8406 often climbs past 32. Range 1–256; default 32. Check with: platform-session plasmashell check")
            enabled: kcm.watchQsgThreads
            from: 1
            to: 256
            value: kcm.qsgThreadThreshold
            onValueModified: kcm.qsgThreadThreshold = value
        }
    }

    Item {
        Layout.fillHeight: true
    }
}
