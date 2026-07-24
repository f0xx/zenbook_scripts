// SPDX-License-Identifier: GPL-2.0-or-later

#include "zenbookplatform.h"

#include <KLocalizedString>

#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QProcess>
#include <QProcessEnvironment>
#include <QStandardPaths>

#ifndef ZENBOOK_SCRIPTS_ROOT
#define ZENBOOK_SCRIPTS_ROOT "/usr/share/zenbook-scripts"
#endif

#ifndef ZENBOOK_KCM_VERSION
#define ZENBOOK_KCM_VERSION "0.0.3"
#endif

K_PLUGIN_CLASS_WITH_JSON(ZenbookPlatform, "kcm_zenbook_platform.json")

ZenbookPlatform::ZenbookPlatform(QObject *parent, const KPluginMetaData &data)
    : KQuickConfigModule(parent, data)
{
    setButtons(KQuickConfigModule::Help);

    m_process = new QProcess(this);
    connect(m_process, &QProcess::finished, this, &ZenbookPlatform::onProcessFinished);

    loadSession();
    refreshProbe();
    refreshDuoStatus();
}

QString ZenbookPlatform::sessionConfigPath() const
{
    const QString configDir =
        QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation) + QStringLiteral("/zenbook-scripts");
    return configDir + QStringLiteral("/session.json");
}

QString ZenbookPlatform::version() const
{
    return QStringLiteral(ZENBOOK_KCM_VERSION);
}

QString ZenbookPlatform::documentationUrl() const
{
    // Public docs only — never bake a local checkout path into the UI.
    // Lives on feature/plasma-kcm-powerdevil until the next RC merges to main.
    return QStringLiteral(
        "https://github.com/f0xx/zenbook_scripts/blob/feature/plasma-kcm-powerdevil/README.plasma.md");
}

QString ZenbookPlatform::resolveScript(const QString &name) const
{
    const QProcessEnvironment env = QProcessEnvironment::systemEnvironment();
    const QStringList candidates = {
        QStringLiteral("/usr/bin/") + name,
        QStringLiteral("/usr/local/bin/") + name,
        env.value(QStringLiteral("ZENBOOK_SCRIPTS_ROOT")) + QStringLiteral("/bin/") + name,
        QStringLiteral(ZENBOOK_SCRIPTS_ROOT) + QStringLiteral("/bin/") + name,
    };

    for (const QString &path : candidates) {
        if (path.isEmpty()) {
            continue;
        }
        if (QFile::exists(path)) {
            return path;
        }
    }
    return {};
}

void ZenbookPlatform::setBusy(bool busy)
{
    if (m_busy == busy) {
        return;
    }
    m_busy = busy;
    Q_EMIT busyChanged();
}

void ZenbookPlatform::setLastError(const QString &error)
{
    if (m_lastError == error) {
        return;
    }
    m_lastError = error;
    Q_EMIT lastErrorChanged();
}

void ZenbookPlatform::runScript(const QString &name, const QStringList &args, const QString &outputProperty)
{
    Q_UNUSED(outputProperty)

    if (m_busy) {
        setLastError(i18n("Another command is still running."));
        return;
    }

    const QString script = resolveScript(name);
    if (script.isEmpty()) {
        setLastError(i18n("Could not find %1 in PATH or zenbook-scripts bin.", name));
        return;
    }

    if (name == QLatin1String("platform-probe")) {
        m_outputTarget = OutputTarget::Probe;
    } else if (name == QLatin1String("platform-duo-dock") && args.value(0) == QLatin1String("status")) {
        m_outputTarget = OutputTarget::DuoStatus;
    } else {
        m_outputTarget = OutputTarget::Command;
    }

    setLastError({});
    setBusy(true);

    m_process->setProgram(script);
    m_process->setArguments(args);
    m_process->setProcessEnvironment(QProcessEnvironment::systemEnvironment());
    m_process->start();
}

void ZenbookPlatform::onProcessFinished(int exitCode, QProcess::ExitStatus status)
{
    setBusy(false);

    const QString stdoutText = QString::fromUtf8(m_process->readAllStandardOutput());
    const QString stderrText = QString::fromUtf8(m_process->readAllStandardError());
    const QString combined =
        stdoutText + (stderrText.isEmpty() ? QString() : QStringLiteral("\n") + stderrText.trimmed());

    if (status != QProcess::NormalExit || exitCode != 0) {
        setLastError(i18n("Command failed (exit %1): %2", exitCode, combined.trimmed()));
    } else {
        setLastError({});
    }

    switch (m_outputTarget) {
    case OutputTarget::Probe:
        m_probeText = combined.trimmed();
        Q_EMIT probeTextChanged();
        break;
    case OutputTarget::DuoStatus:
        m_duoStatusText = combined.trimmed();
        Q_EMIT duoStatusTextChanged();
        break;
    case OutputTarget::Command:
        m_lastCommandOutput = combined.trimmed();
        Q_EMIT lastCommandOutputChanged();
        break;
    }

    if (m_outputTarget == OutputTarget::Command && m_process->program().endsWith(QLatin1String("platform-duo-dock"))) {
        refreshDuoStatus();
    }
}

void ZenbookPlatform::refreshProbe()
{
    runScript(QStringLiteral("platform-probe"), {}, QStringLiteral("probeText"));
}

void ZenbookPlatform::refreshDuoStatus()
{
    runScript(QStringLiteral("platform-duo-dock"), {QStringLiteral("status")}, QStringLiteral("duoStatusText"));
}

void ZenbookPlatform::runDuoDocked()
{
    runScript(QStringLiteral("platform-duo-dock"), {QStringLiteral("docked")}, QStringLiteral("lastCommandOutput"));
}

void ZenbookPlatform::runDuoUndocked()
{
    runScript(QStringLiteral("platform-duo-dock"), {QStringLiteral("undocked")}, QStringLiteral("lastCommandOutput"));
}

void ZenbookPlatform::runScreenSwap()
{
    runScript(QStringLiteral("platform-screen-swap"), {}, QStringLiteral("lastCommandOutput"));
}

QJsonObject ZenbookPlatform::defaultProfileObject() const
{
    QJsonObject presentation;
    presentation.insert(QStringLiteral("restore_after_plasmashell_replace"), true);
    presentation.insert(QStringLiteral("inhibit_backend"), QStringLiteral("auto"));

    QJsonObject plasmashell;
    plasmashell.insert(QStringLiteral("watch_qsg_threads"), false);
    plasmashell.insert(QStringLiteral("auto_replace"), false);
    plasmashell.insert(QStringLiteral("qsg_thread_threshold"), 32);

    QJsonObject profile;
    profile.insert(QStringLiteral("on_sleep"), QJsonArray{QStringLiteral("brightness_save"), QStringLiteral("fan_sleep_pre")});
    profile.insert(QStringLiteral("on_resume"), QJsonArray{
        QStringLiteral("brightness_restore"),
        QStringLiteral("fan_sleep_post"),
        QStringLiteral("touchpad_reassert"),
    });
    profile.insert(QStringLiteral("on_hibernate"), QJsonArray{QStringLiteral("brightness_save")});
    profile.insert(QStringLiteral("presentation"), presentation);
    profile.insert(QStringLiteral("plasmashell"), plasmashell);

    return profile;
}

void ZenbookPlatform::applySessionObject(const QJsonObject &root)
{
    m_activeProfile = root.value(QStringLiteral("active_profile")).toString(QStringLiteral("default"));

    const QJsonObject profiles = root.value(QStringLiteral("profiles")).toObject();
    QJsonObject profile = profiles.value(m_activeProfile).toObject();
    if (profile.isEmpty()) {
        profile = defaultProfileObject();
    }

    const QJsonObject presentation = profile.value(QStringLiteral("presentation")).toObject();
    m_restoreAfterPlasmashellReplace =
        presentation.value(QStringLiteral("restore_after_plasmashell_replace")).toBool(true);

    const QJsonObject plasmashell = profile.value(QStringLiteral("plasmashell")).toObject();
    m_watchQsgThreads = plasmashell.value(QStringLiteral("watch_qsg_threads")).toBool(false);
    m_autoReplacePlasmashell = plasmashell.value(QStringLiteral("auto_replace")).toBool(false);
    m_qsgThreadThreshold = plasmashell.value(QStringLiteral("qsg_thread_threshold")).toInt(32);

    m_sessionDirty = false;
    Q_EMIT sessionChanged();
    Q_EMIT sessionDirtyChanged();
}

void ZenbookPlatform::loadSession()
{
    const QString path = sessionConfigPath();
    QFile file(path);
    if (!file.exists()) {
        applySessionObject(buildSessionObject());
        return;
    }

    if (!file.open(QIODevice::ReadOnly)) {
        setLastError(i18n("Could not read %1", path));
        applySessionObject(buildSessionObject());
        return;
    }

    QJsonParseError parseError;
    const QJsonDocument doc = QJsonDocument::fromJson(file.readAll(), &parseError);
    if (parseError.error != QJsonParseError::NoError || !doc.isObject()) {
        setLastError(i18n("Invalid JSON in %1: %2", path, parseError.errorString()));
        applySessionObject(buildSessionObject());
        return;
    }

    applySessionObject(doc.object());
}

QJsonObject ZenbookPlatform::buildSessionObject() const
{
    QJsonObject presentation;
    presentation.insert(QStringLiteral("restore_after_plasmashell_replace"), m_restoreAfterPlasmashellReplace);
    presentation.insert(QStringLiteral("inhibit_backend"), QStringLiteral("auto"));

    QJsonObject plasmashell;
    plasmashell.insert(QStringLiteral("watch_qsg_threads"), m_watchQsgThreads);
    plasmashell.insert(QStringLiteral("auto_replace"), m_autoReplacePlasmashell);
    plasmashell.insert(QStringLiteral("qsg_thread_threshold"), m_qsgThreadThreshold);

    QJsonObject profile = defaultProfileObject();
    profile.insert(QStringLiteral("presentation"), presentation);
    profile.insert(QStringLiteral("plasmashell"), plasmashell);

    QJsonObject profiles;
    profiles.insert(m_activeProfile, profile);

    QJsonObject root;
    root.insert(QStringLiteral("version"), 1);
    root.insert(QStringLiteral("active_profile"), m_activeProfile);
    root.insert(QStringLiteral("profiles"), profiles);
    return root;
}

bool ZenbookPlatform::saveSession()
{
    const QString path = sessionConfigPath();
    QDir().mkpath(QFileInfo(path).absolutePath());

    QFile file(path);
    if (!file.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
        setLastError(i18n("Could not write %1", path));
        return false;
    }

    const QJsonDocument doc(buildSessionObject());
    file.write(doc.toJson(QJsonDocument::Indented));
    file.close();

    m_sessionDirty = false;
    Q_EMIT sessionDirtyChanged();
    setLastError({});
    return true;
}

void ZenbookPlatform::resetSessionDefaults()
{
    applySessionObject(QJsonObject{
        {QStringLiteral("version"), 1},
        {QStringLiteral("active_profile"), QStringLiteral("default")},
        {QStringLiteral("profiles"), QJsonObject{{QStringLiteral("default"), defaultProfileObject()}}},
    });
    markSessionDirty();
}

void ZenbookPlatform::markSessionDirty()
{
    if (m_sessionDirty) {
        return;
    }
    m_sessionDirty = true;
    Q_EMIT sessionDirtyChanged();
}

void ZenbookPlatform::setRestoreAfterPlasmashellReplace(bool value)
{
    if (m_restoreAfterPlasmashellReplace == value) {
        return;
    }
    m_restoreAfterPlasmashellReplace = value;
    Q_EMIT sessionChanged();
    markSessionDirty();
}

void ZenbookPlatform::setWatchQsgThreads(bool value)
{
    if (m_watchQsgThreads == value) {
        return;
    }
    m_watchQsgThreads = value;
    Q_EMIT sessionChanged();
    markSessionDirty();
}

void ZenbookPlatform::setAutoReplacePlasmashell(bool value)
{
    if (m_autoReplacePlasmashell == value) {
        return;
    }
    m_autoReplacePlasmashell = value;
    Q_EMIT sessionChanged();
    markSessionDirty();
}

void ZenbookPlatform::setQsgThreadThreshold(int value)
{
    if (m_qsgThreadThreshold == value) {
        return;
    }
    m_qsgThreadThreshold = value;
    Q_EMIT sessionChanged();
    markSessionDirty();
}

#include "zenbookplatform.moc"
