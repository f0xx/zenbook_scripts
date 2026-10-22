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
#include <QQueue>
#include <QStandardPaths>
#include <QTimer>

#ifndef ZENBOOK_SCRIPTS_ROOT
#define ZENBOOK_SCRIPTS_ROOT "/usr/share/zenbook-scripts"
#endif

#ifndef ZENBOOK_KCM_VERSION
#define ZENBOOK_KCM_VERSION "0.0.4"
#endif

namespace {

QString readSysfsTrimmed(const QString &path)
{
    QFile f(path);
    if (!f.open(QIODevice::ReadOnly)) {
        return {};
    }
    return QString::fromUtf8(f.readAll()).trimmed();
}

bool dmiLooksLikeDuo(const QString &blob)
{
    const QString u = blob.toUpper();
    return u.contains(QLatin1String("UX8406")) || u.contains(QLatin1String("UX8402"))
        || u.contains(QLatin1String("UX581")) || u.contains(QLatin1String("UX582"));
}

bool usbPogoPresent()
{
    const QDir usb(QStringLiteral("/sys/bus/usb/devices"));
    if (!usb.exists()) {
        return false;
    }
    const QStringList entries = usb.entryList(QDir::Dirs | QDir::NoDotAndDotDot);
    for (const QString &name : entries) {
        const QString base = usb.absoluteFilePath(name);
        const QString vid = readSysfsTrimmed(base + QStringLiteral("/idVendor")).toLower();
        const QString pid = readSysfsTrimmed(base + QStringLiteral("/idProduct")).toLower();
        if (vid == QLatin1String("0b05") && pid == QLatin1String("1b2c")) {
            return true;
        }
    }
    return false;
}

} // namespace

K_PLUGIN_CLASS_WITH_JSON(ZenbookPlatform, "kcm_zenbook_platform.json")

ZenbookPlatform::ZenbookPlatform(QObject *parent, const KPluginMetaData &data)
    : KQuickConfigModule(parent, data)
{
    setButtons(KQuickConfigModule::Apply | KQuickConfigModule::Default | KQuickConfigModule::Help);
    setSupportsInstantApply(false);

    m_process = new QProcess(this);
    connect(m_process, &QProcess::finished, this, &ZenbookPlatform::onProcessFinished);

    detectHardware();
}

void ZenbookPlatform::load()
{
    loadSession();
    loadProfiles();
    loadTouchpadKnobs();
    m_probeText = runScriptSync(QStringLiteral("platform-probe"), {});
    Q_EMIT probeTextChanged();
    m_touchpadStatusText = runScriptSync(QStringLiteral("platform-touchpad"), {QStringLiteral("status")});
    Q_EMIT touchpadStatusTextChanged();
    if (m_hasDuoDock) {
        m_duoStatusText = runScriptSync(QStringLiteral("platform-duo-dock"), {QStringLiteral("status")});
        Q_EMIT duoStatusTextChanged();
    }
    if (m_hasScreenpad) {
        m_screenpadStatusText = runScriptSync(QStringLiteral("screenpad"), {QStringLiteral("status")});
        Q_EMIT screenpadStatusTextChanged();
    }
    updateNeedsSave();
}

void ZenbookPlatform::save()
{
    if (m_sessionDirty) {
        saveSession();
    }
    if (m_profilesDirty) {
        saveProfiles();
    }
    if (m_touchpadDirty) {
        saveTouchpadKnobs();
    }
    updateNeedsSave();
}

void ZenbookPlatform::defaults()
{
    resetSessionDefaults();
    resetProfilesDefaults();
    loadTouchpadKnobs();
    updateNeedsSave();
}

void ZenbookPlatform::updateNeedsSave()
{
    setNeedsSave(m_sessionDirty || m_profilesDirty || m_touchpadDirty);
}

void ZenbookPlatform::detectHardware()
{
    const QString product = readSysfsTrimmed(QStringLiteral("/sys/class/dmi/id/product_name"));
    const QString board = readSysfsTrimmed(QStringLiteral("/sys/class/dmi/id/board_name"));
    m_dmiProduct = product.isEmpty() ? QStringLiteral("unknown") : product;
    const QString blob = product + QLatin1Char(' ') + board;

    m_hasScreenpad = QFile::exists(QStringLiteral("/sys/class/backlight/asus_screenpad"));
    m_hasDuoDock = dmiLooksLikeDuo(blob) || usbPogoPresent();
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
    return QStringLiteral("https://github.com/f0xx/zenbook_scripts/blob/main/README.plasma.md");
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

QString ZenbookPlatform::runScriptSync(const QString &name, const QStringList &args) const
{
    const QString script = resolveScript(name);
    if (script.isEmpty()) {
        return i18n("Could not find %1 in PATH or zenbook-scripts bin.", name);
    }
    QProcess proc;
    proc.setProgram(script);
    proc.setArguments(args);
    proc.setProcessEnvironment(QProcessEnvironment::systemEnvironment());
    proc.start();
    if (!proc.waitForFinished(20000)) {
        proc.kill();
        return i18n("Timed out running %1", name);
    }
    const QString stdoutText = QString::fromUtf8(proc.readAllStandardOutput());
    const QString stderrText = QString::fromUtf8(proc.readAllStandardError());
    const QString combined =
        stdoutText + (stderrText.isEmpty() ? QString() : QStringLiteral("\n") + stderrText.trimmed());
    if (proc.exitStatus() != QProcess::NormalExit || proc.exitCode() != 0) {
        return i18n("Failed (exit %1):\n%2", proc.exitCode(), combined.trimmed());
    }
    return combined.trimmed();
}

void ZenbookPlatform::runScript(const QString &name, const QStringList &args, const QString &outputProperty)
{
    Q_UNUSED(outputProperty)
    const OutputTarget target = outputTargetFor(name, args);
    if (m_busy) {
        m_pendingScripts.enqueue(PendingScript{name, args, target});
        return;
    }
    startScript(name, args, target);
}

ZenbookPlatform::OutputTarget ZenbookPlatform::outputTargetFor(const QString &name, const QStringList &args) const
{
    if (name == QLatin1String("platform-probe")) {
        return OutputTarget::Probe;
    }
    if (name == QLatin1String("platform-duo-dock") && args.value(0) == QLatin1String("status")) {
        return OutputTarget::DuoStatus;
    }
    if (name == QLatin1String("screenpad") && args.value(0) == QLatin1String("status")) {
        return OutputTarget::ScreenpadStatus;
    }
    if (name == QLatin1String("platform-touchpad") && args.value(0) == QLatin1String("status")) {
        return OutputTarget::TouchpadStatus;
    }
    return OutputTarget::Command;
}

void ZenbookPlatform::startScript(const QString &name, const QStringList &args, OutputTarget target)
{
    const QString script = resolveScript(name);
    if (script.isEmpty()) {
        setLastError(i18n("Could not find %1 in PATH or zenbook-scripts bin.", name));
        if (target == OutputTarget::TouchpadStatus) {
            m_touchpadStatusText = i18n("(platform-touchpad not found)");
            Q_EMIT touchpadStatusTextChanged();
        }
        drainPendingScripts();
        return;
    }

    m_outputTarget = target;
    setLastError({});
    setBusy(true);

    m_process->setProgram(script);
    m_process->setArguments(args);
    m_process->setProcessEnvironment(QProcessEnvironment::systemEnvironment());
    m_process->start();
}

void ZenbookPlatform::drainPendingScripts()
{
    if (m_busy || m_pendingScripts.isEmpty()) {
        return;
    }
    const PendingScript next = m_pendingScripts.dequeue();
    startScript(next.name, next.args, next.target);
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

    const QString statusBody = combined.trimmed();

    switch (m_outputTarget) {
    case OutputTarget::Probe:
        m_probeText = statusBody;
        Q_EMIT probeTextChanged();
        break;
    case OutputTarget::DuoStatus:
        m_duoStatusText = statusBody.isEmpty() ? i18n("(no status)") : statusBody;
        Q_EMIT duoStatusTextChanged();
        break;
    case OutputTarget::ScreenpadStatus:
        m_screenpadStatusText = statusBody.isEmpty() ? i18n("(no status)") : statusBody;
        Q_EMIT screenpadStatusTextChanged();
        break;
    case OutputTarget::TouchpadStatus:
        if (status != QProcess::NormalExit || exitCode != 0) {
            m_touchpadStatusText =
                i18n("Status failed (exit %1):\n%2", exitCode, statusBody.isEmpty() ? i18n("(no output)") : statusBody);
        } else {
            m_touchpadStatusText = statusBody.isEmpty() ? i18n("(no status output)") : statusBody;
        }
        Q_EMIT touchpadStatusTextChanged();
        break;
    case OutputTarget::Command:
        m_lastCommandOutput = statusBody;
        Q_EMIT lastCommandOutputChanged();
        break;
    }

    const QString prog = m_process->program();
    if (m_outputTarget == OutputTarget::Command && prog.endsWith(QLatin1String("platform-duo-dock"))) {
        refreshDuoStatus();
    } else if (m_outputTarget == OutputTarget::Command && prog.endsWith(QLatin1String("screenpad"))) {
        refreshScreenpadStatus();
    } else if (m_outputTarget == OutputTarget::Command && prog.endsWith(QLatin1String("platform-touchpad"))) {
        refreshTouchpadStatus();
    }

    drainPendingScripts();
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

void ZenbookPlatform::refreshScreenpadStatus()
{
    runScript(QStringLiteral("screenpad"), {QStringLiteral("status")}, QStringLiteral("screenpadStatusText"));
}

void ZenbookPlatform::runScreenpadOn()
{
    runScript(QStringLiteral("screenpad"), {QStringLiteral("on")}, QStringLiteral("lastCommandOutput"));
}

void ZenbookPlatform::runScreenpadOff()
{
    runScript(QStringLiteral("screenpad"), {QStringLiteral("off")}, QStringLiteral("lastCommandOutput"));
}

void ZenbookPlatform::runScreenpadSync()
{
    runScript(QStringLiteral("screenpad"), {QStringLiteral("sync")}, QStringLiteral("lastCommandOutput"));
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
    updateNeedsSave();
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
    updateNeedsSave();
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

QString ZenbookPlatform::profilesConfigPath() const
{
    const QString configDir =
        QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation) + QStringLiteral("/zenbook-scripts");
    return configDir + QStringLiteral("/profiles.json");
}

QJsonObject ZenbookPlatform::defaultProfilesObject() const
{
    const QString examplePaths[] = {
        QStringLiteral("/usr/share/zenbook-scripts/profiles.json.example"),
        QStringLiteral("/usr/local/share/zenbook-scripts/profiles.json.example"),
        QStringLiteral(ZENBOOK_SCRIPTS_ROOT) + QStringLiteral("/profiles.json.example"),
    };
    for (const QString &path : examplePaths) {
        QFile file(path);
        if (!file.open(QIODevice::ReadOnly)) {
            continue;
        }
        QJsonParseError parseError;
        const QJsonDocument doc = QJsonDocument::fromJson(file.readAll(), &parseError);
        if (parseError.error == QJsonParseError::NoError && doc.isObject()) {
            return doc.object();
        }
    }
    return QJsonObject{
        {QStringLiteral("version"), 1},
        {QStringLiteral("active_mode"), QStringLiteral("auto")},
        {QStringLiteral("notifications"), QJsonObject{
            {QStringLiteral("enabled"), true},
            {QStringLiteral("on_mode_switch"), true},
        }},
    };
}

void ZenbookPlatform::loadProfiles()
{
    const QString path = profilesConfigPath();
    QFile file(path);
    if (!file.exists()) {
        m_profilesRoot = defaultProfilesObject();
        m_profilesDirty = false;
        Q_EMIT profilesChanged();
        Q_EMIT profilesDirtyChanged();
        updateNeedsSave();
        return;
    }
    if (!file.open(QIODevice::ReadOnly)) {
        setLastError(i18n("Could not read %1", path));
        m_profilesRoot = defaultProfilesObject();
        Q_EMIT profilesChanged();
        return;
    }
    QJsonParseError parseError;
    const QJsonDocument doc = QJsonDocument::fromJson(file.readAll(), &parseError);
    if (parseError.error != QJsonParseError::NoError || !doc.isObject()) {
        setLastError(i18n("Invalid profiles JSON in %1: %2", path, parseError.errorString()));
        m_profilesRoot = defaultProfilesObject();
    } else {
        m_profilesRoot = doc.object();
    }
    m_profilesDirty = false;
    Q_EMIT profilesChanged();
    Q_EMIT profilesDirtyChanged();
    updateNeedsSave();
}

QString ZenbookPlatform::profilesJson() const
{
    return QString::fromUtf8(QJsonDocument(m_profilesRoot).toJson(QJsonDocument::Indented));
}

void ZenbookPlatform::setProfilesJson(const QString &json)
{
    QJsonParseError parseError;
    const QJsonDocument doc = QJsonDocument::fromJson(json.toUtf8(), &parseError);
    if (parseError.error != QJsonParseError::NoError || !doc.isObject()) {
        setLastError(i18n("Invalid profiles JSON: %1", parseError.errorString()));
        return;
    }
    m_profilesRoot = doc.object();
    Q_EMIT profilesChanged();
    markProfilesDirty();
}

bool ZenbookPlatform::saveProfiles()
{
    const QString path = profilesConfigPath();
    QDir().mkpath(QFileInfo(path).absolutePath());
    QFile file(path);
    if (!file.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
        setLastError(i18n("Could not write %1", path));
        return false;
    }
    file.write(QJsonDocument(m_profilesRoot).toJson(QJsonDocument::Indented));
    file.close();
    m_profilesDirty = false;
    Q_EMIT profilesDirtyChanged();
    setLastError({});
    updateNeedsSave();
    return true;
}

void ZenbookPlatform::resetProfilesDefaults()
{
    m_profilesRoot = defaultProfilesObject();
    m_profilesDirty = true;
    Q_EMIT profilesChanged();
    Q_EMIT profilesDirtyChanged();
}

void ZenbookPlatform::markProfilesDirty()
{
    if (m_profilesDirty) {
        return;
    }
    m_profilesDirty = true;
    Q_EMIT profilesDirtyChanged();
    updateNeedsSave();
}

void ZenbookPlatform::refreshTouchpadStatus()
{
    runScript(QStringLiteral("platform-touchpad"), {QStringLiteral("status")}, QStringLiteral("touchpadStatusText"));
}

void ZenbookPlatform::openTouchpadTuner()
{
    const QString gui = resolveScript(QStringLiteral("platform-touchpad-gui"));
    if (gui.isEmpty()) {
        setLastError(i18n("platform-touchpad-gui not found"));
        return;
    }
    if (!QProcess::startDetached(gui, {})) {
        setLastError(i18n("Could not start platform-touchpad-gui"));
    }
}

QString ZenbookPlatform::touchpadConfigPath() const
{
    const QString userCfg =
        QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation)
        + QStringLiteral("/zenbook-scripts/touchpad.json");
    if (QFile::exists(userCfg)) {
        return userCfg;
    }
    return QStringLiteral("/etc/zenbook-scripts/touchpad.json");
}

void ZenbookPlatform::startTouchpadLiveFilter()
{
    const QString script = resolveScript(QStringLiteral("platform-touchpad"));
    if (script.isEmpty()) {
        setLastError(i18n("platform-touchpad not found"));
        return;
    }
    const QString cfg = touchpadConfigPath();
    const QStringList args = {QStringLiteral("-n"),
                              script,
                              QStringLiteral("run"),
                              QStringLiteral("--replace"),
                              QStringLiteral("--config"),
                              cfg};
    if (!QProcess::startDetached(QStringLiteral("sudo"), args)) {
        setLastError(i18n("Could not start live filter (sudo failed)"));
        return;
    }
    setLastError({});
    QTimer::singleShot(700, this, &ZenbookPlatform::verifyLiveFilterStarted);
}

void ZenbookPlatform::verifyLiveFilterStarted()
{
    const QString status =
        runScriptSync(QStringLiteral("platform-touchpad"), {QStringLiteral("status")});
    m_touchpadStatusText = status;
    Q_EMIT touchpadStatusTextChanged();
    const bool running = status.contains(QStringLiteral("live:     running"))
        || status.contains(QStringLiteral("live:\trunning"));
    if (!running) {
        setLastError(
            i18n("Live filter did not start — need passwordless sudo "
                 "(sudo -n platform-touchpad run) or install contrib/udev/99-uinput.rules "
                 "and add your user to the input group."));
    }
}

void ZenbookPlatform::stopTouchpadLiveFilter()
{
    const QString script = resolveScript(QStringLiteral("platform-touchpad"));
    if (script.isEmpty()) {
        setLastError(i18n("platform-touchpad not found"));
        return;
    }
    QProcess proc;
    proc.start(QStringLiteral("sudo"), {QStringLiteral("-n"), script, QStringLiteral("stop")});
    if (!proc.waitForFinished(10000)) {
        proc.kill();
        setLastError(i18n("Timed out stopping live filter"));
        refreshTouchpadStatus();
        return;
    }
    const QString combined =
        QString::fromUtf8(proc.readAllStandardOutput() + proc.readAllStandardError()).trimmed();
    if (proc.exitStatus() != QProcess::NormalExit || proc.exitCode() != 0) {
        setLastError(i18n("Stop failed (exit %1): %2", proc.exitCode(), combined));
    } else {
        setLastError({});
    }
    refreshTouchpadStatus();
}

void ZenbookPlatform::applyActiveProfile()
{
    saveProfiles();
    const QString mode = m_profilesRoot.value(QStringLiteral("active_mode")).toString(QStringLiteral("auto"));
    const QString helper = resolveScript(QStringLiteral("platform-profiles"));
    if (helper.isEmpty()) {
        setLastError(i18n("platform-profiles not found"));
        return;
    }
    runScript(helper, {QStringLiteral("set"), mode}, QStringLiteral("lastCommandOutput"));
}

void ZenbookPlatform::loadTouchpadKnobs()
{
    const QString helper = resolveScript(QStringLiteral("platform-touchpad-kcm"));
    if (helper.isEmpty()) {
        m_touchpadKnobsJson = QStringLiteral("{}");
        Q_EMIT touchpadKnobsChanged();
        return;
    }
    QProcess proc;
    proc.start(helper, {QStringLiteral("export")});
    if (!proc.waitForFinished(8000) || proc.exitCode() != 0) {
        setLastError(i18n("platform-touchpad-kcm export failed"));
        return;
    }
    m_touchpadKnobsJson = QString::fromUtf8(proc.readAllStandardOutput()).trimmed();
    m_touchpadDirty = false;
    Q_EMIT touchpadKnobsChanged();
    Q_EMIT touchpadDirtyChanged();
    setLastError({});
}

void ZenbookPlatform::setTouchpadKnobsJson(const QString &json)
{
    if (m_touchpadKnobsJson == json) {
        return;
    }
    m_touchpadKnobsJson = json;
    if (!m_touchpadDirty) {
        m_touchpadDirty = true;
        Q_EMIT touchpadDirtyChanged();
        updateNeedsSave();
    }
    Q_EMIT touchpadKnobsChanged();
}

bool ZenbookPlatform::saveTouchpadKnobs()
{
    const QString helper = resolveScript(QStringLiteral("platform-touchpad-kcm"));
    if (helper.isEmpty()) {
        setLastError(i18n("platform-touchpad-kcm not found"));
        return false;
    }
    QProcess proc;
    proc.start(helper, {QStringLiteral("import"), QStringLiteral("-")});
    proc.write(m_touchpadKnobsJson.toUtf8());
    proc.closeWriteChannel();
    if (!proc.waitForFinished(8000) || proc.exitCode() != 0) {
        setLastError(i18n("platform-touchpad-kcm import failed: %1", QString::fromUtf8(proc.readAllStandardError())));
        return false;
    }
    m_touchpadDirty = false;
    Q_EMIT touchpadDirtyChanged();
    refreshTouchpadStatus();
    // Restart live filter when profile knobs changed and daemon was running.
    if (m_touchpadStatusText.contains(QStringLiteral("live:     running"))) {
        startTouchpadLiveFilter();
    }
    setLastError({});
    updateNeedsSave();
    return true;
}

#include "zenbookplatform.moc"
