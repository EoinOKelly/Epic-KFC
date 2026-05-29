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

QString nextValue(const QStringList& arguments, int index) {
    const int valueIndex = index + 1;
    if (valueIndex >= arguments.size()) {
        return {};
    }
    return arguments.at(valueIndex);
}
}

Result<StartupConfig> StartupConfigParser::parse(const QStringList& arguments) const {
    StartupConfig config;
    config.statePath = defaultStatePath();

    for (int index = 1; index < arguments.size(); ++index) {
        const QString argument = arguments.at(index);
        if (argument == AppText::HelpFlag) {
            return Result<StartupConfig>::failure({ErrorCode::InvalidConfiguration, AppText::StartupUsage});
        }

        if (argument == AppText::ModeFlag) {
            const QString mode = nextValue(arguments, index).toLower();
            if (mode == AppText::MockMode) {
                config.mode = ClientMode::Mock;
            } else if (mode == AppText::RealMode) {
                config.mode = ClientMode::Real;
            } else {
                return Result<StartupConfig>::failure({ErrorCode::InvalidConfiguration, AppText::InvalidMode});
            }
            ++index;
            continue;
        }

        if (argument == AppText::ApiUrlFlag) {
            config.apiUrl = nextValue(arguments, index);
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
