# SPDX-License-Identifier: GPL-2.0-or-later

cmake_minimum_required(VERSION 3.16)

set(QT_MIN_VERSION "6.5.0")
set(KF6_MIN_VERSION "6.0.0")
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED TRUE)

project(kcm_zenbook_platform VERSION 0.0.3 LANGUAGES CXX)

find_package(ECM ${KF6_MIN_VERSION} REQUIRED NO_MODULE)
set(CMAKE_MODULE_PATH ${ECM_MODULE_PATH})

include(KDEInstallDirs)
include(KDECompilerSettings NO_POLICY_SCOPE)
include(KDECMakeSettings)

find_package(Qt6 ${QT_MIN_VERSION} CONFIG REQUIRED COMPONENTS Core Quick Gui Qml)

find_package(KF6 ${KF6_MIN_VERSION} REQUIRED COMPONENTS
    CoreAddons
    I18n
    KCMUtils
)

# Gentoo installs Plasma KCMs under Qt's plugin dir (lib64/qt6/plugins), not
# plain lib64/plugins — otherwise System Settings / kcmshell6 --list miss them.
if(DEFINED Qt6_DIR)
    get_filename_component(_qt6_prefix "${Qt6_DIR}/../../.." ABSOLUTE)
endif()
if(EXISTS "${_qt6_prefix}/lib64/qt6/plugins")
    set(KDE_INSTALL_PLUGINDIR "lib64/qt6/plugins" CACHE PATH "" FORCE)
elseif(EXISTS "${_qt6_prefix}/lib/qt6/plugins")
    set(KDE_INSTALL_PLUGINDIR "lib/qt6/plugins" CACHE PATH "" FORCE)
endif()

# Repo root for dev-time CLI fallback (override with -DZENBOOK_SCRIPTS_ROOT=...)
if(NOT ZENBOOK_SCRIPTS_ROOT)
    get_filename_component(ZENBOOK_SCRIPTS_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../.." ABSOLUTE)
endif()

add_subdirectory(src)
