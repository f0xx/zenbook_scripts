// SPDX-License-Identifier: GPL-2.0-or-later

#pragma once

#include <KQuickConfigModule>

#include <QProcess>

class ZenbookPlatform : public KQuickConfigModule
{
    Q_OBJECT

    Q_PROPERTY(QString probeText READ probeText NOTIFY probeTextChanged)
    Q_PROPERTY(QString duoStatusText READ duoStatusText NOTIFY duoStatusTextChanged)
    Q_PROPERTY(QString screenpadStatusText READ screenpadStatusText NOTIFY screenpadStatusTextChanged)
    Q_PROPERTY(QString lastCommandOutput READ lastCommandOutput NOTIFY lastCommandOutputChanged)
    Q_PROPERTY(QString lastError READ lastError NOTIFY lastErrorChanged)
    Q_PROPERTY(bool busy READ busy NOTIFY busyChanged)

    Q_PROPERTY(bool showDisplaysTab READ showDisplaysTab CONSTANT)
    Q_PROPERTY(bool hasDuoDock READ hasDuoDock CONSTANT)
    Q_PROPERTY(bool hasScreenpad READ hasScreenpad CONSTANT)
    Q_PROPERTY(QString dmiProduct READ dmiProduct CONSTANT)

    Q_PROPERTY(QString sessionConfigPath READ sessionConfigPath CONSTANT)
    Q_PROPERTY(QString activeProfile READ activeProfile NOTIFY sessionChanged)
    Q_PROPERTY(bool restoreAfterPlasmashellReplace READ restoreAfterPlasmashellReplace WRITE setRestoreAfterPlasmashellReplace NOTIFY sessionChanged)
    Q_PROPERTY(bool watchQsgThreads READ watchQsgThreads WRITE setWatchQsgThreads NOTIFY sessionChanged)
    Q_PROPERTY(bool autoReplacePlasmashell READ autoReplacePlasmashell WRITE setAutoReplacePlasmashell NOTIFY sessionChanged)
    Q_PROPERTY(int qsgThreadThreshold READ qsgThreadThreshold WRITE setQsgThreadThreshold NOTIFY sessionChanged)
    Q_PROPERTY(bool sessionDirty READ sessionDirty NOTIFY sessionDirtyChanged)

    Q_PROPERTY(QString version READ version CONSTANT)
    Q_PROPERTY(QString documentationUrl READ documentationUrl CONSTANT)

public:
    explicit ZenbookPlatform(QObject *parent, const KPluginMetaData &data);

    QString probeText() const
    {
        return m_probeText;
    }
    QString duoStatusText() const
    {
        return m_duoStatusText;
    }
    QString screenpadStatusText() const
    {
        return m_screenpadStatusText;
    }
    QString lastCommandOutput() const
    {
        return m_lastCommandOutput;
    }
    QString lastError() const
    {
        return m_lastError;
    }
    bool busy() const
    {
        return m_busy;
    }

    bool showDisplaysTab() const
    {
        return m_hasDuoDock || m_hasScreenpad;
    }
    bool hasDuoDock() const
    {
        return m_hasDuoDock;
    }
    bool hasScreenpad() const
    {
        return m_hasScreenpad;
    }
    QString dmiProduct() const
    {
        return m_dmiProduct;
    }

    QString sessionConfigPath() const;
    QString activeProfile() const
    {
        return m_activeProfile;
    }
    bool restoreAfterPlasmashellReplace() const
    {
        return m_restoreAfterPlasmashellReplace;
    }
    bool watchQsgThreads() const
    {
        return m_watchQsgThreads;
    }
    bool autoReplacePlasmashell() const
    {
        return m_autoReplacePlasmashell;
    }
    int qsgThreadThreshold() const
    {
        return m_qsgThreadThreshold;
    }
    bool sessionDirty() const
    {
        return m_sessionDirty;
    }

    QString version() const;
    QString documentationUrl() const;

    void setRestoreAfterPlasmashellReplace(bool value);
    void setWatchQsgThreads(bool value);
    void setAutoReplacePlasmashell(bool value);
    void setQsgThreadThreshold(int value);

    Q_INVOKABLE void refreshProbe();
    Q_INVOKABLE void refreshDuoStatus();
    Q_INVOKABLE void runDuoDocked();
    Q_INVOKABLE void runDuoUndocked();
    Q_INVOKABLE void runScreenSwap();
    Q_INVOKABLE void refreshScreenpadStatus();
    Q_INVOKABLE void runScreenpadOn();
    Q_INVOKABLE void runScreenpadOff();
    Q_INVOKABLE void runScreenpadSync();
    Q_INVOKABLE void loadSession();
    Q_INVOKABLE bool saveSession();
    Q_INVOKABLE void resetSessionDefaults();

Q_SIGNALS:
    void probeTextChanged();
    void duoStatusTextChanged();
    void screenpadStatusTextChanged();
    void lastCommandOutputChanged();
    void lastErrorChanged();
    void busyChanged();
    void sessionChanged();
    void sessionDirtyChanged();

private Q_SLOTS:
    void onProcessFinished(int exitCode, QProcess::ExitStatus status);

private:
    void detectHardware();
    QString resolveScript(const QString &name) const;
    void runScript(const QString &name, const QStringList &args, const QString &outputProperty);
    void setBusy(bool busy);
    void setLastError(const QString &error);
    void applySessionObject(const QJsonObject &root);
    QJsonObject buildSessionObject() const;
    QJsonObject defaultProfileObject() const;
    void markSessionDirty();

    QString m_probeText;
    QString m_duoStatusText;
    QString m_screenpadStatusText;
    QString m_lastCommandOutput;
    QString m_lastError;
    bool m_busy = false;

    bool m_hasDuoDock = false;
    bool m_hasScreenpad = false;
    QString m_dmiProduct;

    QString m_activeProfile = QStringLiteral("default");
    bool m_restoreAfterPlasmashellReplace = true;
    bool m_watchQsgThreads = false;
    bool m_autoReplacePlasmashell = false;
    int m_qsgThreadThreshold = 32;
    bool m_sessionDirty = false;

    QProcess *m_process = nullptr;
    enum class OutputTarget {
        Probe,
        DuoStatus,
        ScreenpadStatus,
        Command,
    };
    OutputTarget m_outputTarget = OutputTarget::Command;
};
