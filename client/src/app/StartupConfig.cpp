#include "app/StartupConfig.h"

#include "support/ClientConstants.h"

#include <QDir>
#include <QStandardPaths>
#include <QUrl>

namespace {
QString defaultStatePath() {
    QString basePath = QStandardPaths::writableLocation(QStandardPaths::AppDataLocation);
    if (basePath.isEmpty()) {
        basePath = QDir::currentPath();
    }
    return QDir(basePath).filePath(AppText::DefaultStateFile);
}

QString nextValue(const std::vector<QString>& arguments, int index) {
    const int valueIndex = index + 1;
    if (valueIndex >= static_cast<int>(arguments.size())) {
        return {};
    }
    return arguments.at(valueIndex);
}
}

Result<StartupConfig> StartupConfigParser::parse(const std::vector<QString>& arguments) const {
    StartupConfig config;
    config.mode = ClientMode::Real;
    config.apiUrl = AppText::DefaultApiUrl;
    config.statePath = defaultStatePath();
    bool debugMode = false;
    bool realModeProvided = false;
    bool apiUrlProvided = false;

    for (int index = 1; index < static_cast<int>(arguments.size()); ++index) {
        const QString argument = arguments.at(index);
        if (argument == AppText::HelpFlag) {
            return Result<StartupConfig>::failure({ErrorCode::InvalidConfiguration, AppText::StartupUsage});
        }

        if (argument == AppText::DebugFlag) {
            if (realModeProvided) {
                return Result<StartupConfig>::failure({ErrorCode::InvalidConfiguration, AppText::DebugRealModeConflict});
            }
            debugMode = true;
            config.mode = ClientMode::Mock;
            config.apiUrl.clear();
            continue;
        }

        if (argument == AppText::ModeFlag) {
            const QString mode = nextValue(arguments, index).toLower();
            if (mode == AppText::MockMode) {
                config.mode = ClientMode::Mock;
                config.apiUrl.clear();
            } else if (mode == AppText::RealMode) {
                if (debugMode) {
                    return Result<StartupConfig>::failure({ErrorCode::InvalidConfiguration, AppText::DebugRealModeConflict});
                }
                realModeProvided = true;
                config.mode = ClientMode::Real;
                if (!apiUrlProvided) {
                    config.apiUrl = AppText::DefaultApiUrl;
                }
            } else {
                return Result<StartupConfig>::failure({ErrorCode::InvalidConfiguration, AppText::InvalidMode});
            }
            ++index;
            continue;
        }

        if (argument == AppText::ApiUrlFlag) {
            if (debugMode) {
                return Result<StartupConfig>::failure({ErrorCode::InvalidConfiguration, AppText::DebugApiUrlConflict});
            }
            config.apiUrl = nextValue(arguments, index);
            apiUrlProvided = true;
            ++index;
            continue;
        }

        if (argument == AppText::DeviceIdFlag) {
            bool parsed = false;
            const int deviceId = nextValue(arguments, index).toInt(&parsed);
            if (!parsed || deviceId <= 0) {
                return Result<StartupConfig>::failure({ErrorCode::InvalidConfiguration, AppText::InvalidDeviceId});
            }
            config.deviceId = deviceId;
            ++index;
            continue;
        }

        if (argument == AppText::StatePathFlag) {
            config.statePath = nextValue(arguments, index);
            ++index;
            continue;
        }

        return Result<StartupConfig>::failure({
            ErrorCode::InvalidConfiguration,
            QString(CommandText::UnknownCommand).arg(argument, AppText::StartupUsage)
        });
    }

    if (debugMode && apiUrlProvided) {
        return Result<StartupConfig>::failure({ErrorCode::InvalidConfiguration, AppText::DebugApiUrlConflict});
    }

    if (config.mode == ClientMode::Real) {
        if (config.apiUrl.isEmpty()) {
            return Result<StartupConfig>::failure({ErrorCode::InvalidConfiguration, AppText::MissingRealApiUrl});
        }

        const QUrl url(config.apiUrl);
        const bool tlsProtected = url.scheme() == AppText::HttpsScheme;
        if (!tlsProtected) {
            return Result<StartupConfig>::failure({ErrorCode::InvalidConfiguration, AppText::TlsRequired});
        }
    }

    return Result<StartupConfig>::success(config);
}
