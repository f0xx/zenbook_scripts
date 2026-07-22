# SPDX-License-Identifier: GPL-2.0-or-later

kcmutils_add_qml_kcm(kcm_zenbook_platform)

target_sources(kcm_zenbook_platform PRIVATE
    zenbookplatform.cpp
    zenbookplatform.h
)

target_compile_definitions(kcm_zenbook_platform PRIVATE
    ZENBOOK_SCRIPTS_ROOT="${ZENBOOK_SCRIPTS_ROOT}"
    ZENBOOK_KCM_VERSION="${PROJECT_VERSION}"
)

target_link_libraries(kcm_zenbook_platform PRIVATE
    Qt::Core
    Qt::Gui
    Qt::Qml
    Qt::Quick
    KF6::CoreAddons
    KF6::I18n
    KF6::KCMUtilsQuick
)
