#include "app/ClientController.h"
#include "app/CommandRouter.h"
#include "app/EventBus.h"
#include "app/StartupConfig.h"
#include "console/ConsoleInputWorker.h"
#include "console/ConsolePresenter.h"
#include "crypto/MockCryptoProvider.h"
#include "crypto/NativeSignalCryptoProvider.h"
#include "domain/Models.h"
#include "gateways/Gateways.h"
#include "gateways/HttpGateways.h"
#include "services/Services.h"
#include "storage/JsonLocalStore.h"
#include "support/ClientConstants.h"

#include <QCoreApplication>
#include <QDebug>
#include <QLoggingCategory>
#include <QTextStream>

#include <memory>
#include <vector>

namespace {
bool showRawQtMessages = false;
const QString Http2LogCategory = QStringLiteral("qt.network.http2");
const QString NetworkLogCategoryPrefix = QStringLiteral("qt.network");

std::vector<QString> applicationArguments() {
    const QStringList qtArguments = QCoreApplication::arguments();
    return {qtArguments.cbegin(), qtArguments.cend()};
}

bool isNoisyNetworkLog(const QMessageLogContext& context) {
    const QString category = QString::fromUtf8(context.category);
    return category == Http2LogCategory || category.startsWith(NetworkLogCategoryPrefix);
}

void clientQtMessageHandler(QtMsgType type, const QMessageLogContext& context, const QString& message) {
    const bool shouldHideWarning = type == QtWarningMsg && !showRawQtMessages;
    const bool shouldHideNetworkLog = type == QtWarningMsg && isNoisyNetworkLog(context);
    if (shouldHideWarning || shouldHideNetworkLog) {
        return;
    }
    QTextStream(stderr) << message << '\n';
}
}

int main(int argc, char* argv[]) {
    QCoreApplication app(argc, argv);
    QCoreApplication::setApplicationName(AppText::ApplicationName);
    QCoreApplication::setOrganizationName(AppText::OrganizationName);
    registerClientMetaTypes();

    StartupConfigParser configParser;
    const auto parsedConfig = configParser.parse(applicationArguments());
    if (parsedConfig.failed()) {
        QTextStream(stderr) << parsedConfig.error().message << '\n';
        return 1;
    }
    const StartupConfig config = parsedConfig.value();
    showRawQtMessages = config.showRawErrors;
    qInstallMessageHandler(clientQtMessageHandler);
    QLoggingCategory::setFilterRules(QStringLiteral("qt.network.warning=false\nqt.network.http2.warning=false\n"));

    EventBus events;
    JsonLocalStore store(config.statePath, config.mode == ClientMode::Real);
    const bool accountScopedState = config.mode == ClientMode::Real && !config.statePathExplicit;
    if (accountScopedState) {
        const auto lastAccount = store.lastAccountId();
        if (lastAccount.succeeded() && lastAccount.value().has_value()) {
            const auto scoped = store.useAccountScopedPath(*lastAccount.value(), false);
            if (scoped.failed()) {
                QTextStream(stderr) << scoped.error().message << '\n';
                return 1;
            }

            QTextStream(stdout) << "Enter local state password to restore the previous session, or press Enter to skip.\n";
            QTextStream(stdout) << AppText::PasswordPrompt;
            QTextStream(stdout).flush();
            QTextStream input(stdin);
            const QString password = input.readLine();
            if (!password.isEmpty()) {
                store.setSecretPassphrase(password);
                const auto loaded = store.reload();
                if (loaded.failed()) {
                    QTextStream(stderr) << loaded.error().message << '\n';
                    return 1;
                }
            }
        }
    }
    std::unique_ptr<ICryptoProvider> cryptoProvider;
    std::unique_ptr<HttpClient> httpClient;
    std::unique_ptr<IAuthGateway> httpAuthGateway;
    std::unique_ptr<IKeyGateway> httpKeyGateway;
    std::unique_ptr<IUserDirectoryGateway> httpUserDirectoryGateway;
    std::unique_ptr<IMessageGateway> httpMessageGateway;
    std::unique_ptr<IAuthGateway> mockAuthGateway;
    std::unique_ptr<IKeyGateway> mockKeyGateway;
    std::unique_ptr<IUserDirectoryGateway> mockUserDirectoryGateway;
    std::unique_ptr<IMessageGateway> mockMessageGateway;

    IAuthGateway* authGateway = nullptr;
    IKeyGateway* keyGateway = nullptr;
    IUserDirectoryGateway* userDirectoryGateway = nullptr;
    IMessageGateway* messageGateway = nullptr;

    if (config.mode == ClientMode::Real) {
        auto nativeCryptoProvider = std::make_unique<NativeSignalCryptoProvider>();
        if (!nativeCryptoProvider->isAvailable()) {
            QTextStream(stderr) << AppText::NativeCryptoUnavailable << '\n';
            return 1;
        }
        cryptoProvider = std::move(nativeCryptoProvider);
        httpClient = std::make_unique<HttpClient>(config.apiUrl);
        httpAuthGateway = std::make_unique<HttpAuthGateway>(*httpClient);
        httpKeyGateway = std::make_unique<HttpKeyGateway>(*httpClient);
        httpUserDirectoryGateway = std::make_unique<HttpUserDirectoryGateway>(*httpClient);
        httpMessageGateway = std::make_unique<HttpMessageGateway>(*httpClient);
        authGateway = httpAuthGateway.get();
        keyGateway = httpKeyGateway.get();
        userDirectoryGateway = httpUserDirectoryGateway.get();
        messageGateway = httpMessageGateway.get();
    } else {
        cryptoProvider = std::make_unique<MockCryptoProvider>();
        mockAuthGateway = std::make_unique<MockAuthGateway>();
        mockKeyGateway = std::make_unique<MockKeyGateway>();
        mockUserDirectoryGateway = std::make_unique<MockUserDirectoryGateway>();
        mockMessageGateway = std::make_unique<MockMessageGateway>();
        authGateway = mockAuthGateway.get();
        keyGateway = mockKeyGateway.get();
        userDirectoryGateway = mockUserDirectoryGateway.get();
        messageGateway = mockMessageGateway.get();
    }

    SessionService sessionService(events, *authGateway, store, accountScopedState);
    if (httpClient) {
        if (const auto session = sessionService.currentSession(); session.has_value()) {
            httpClient->setTokens(session->tokens);
        }
        httpClient->setTokenUpdateHandler([&sessionService](const TokenSet& tokens) {
            sessionService.updateTokens(tokens);
        });
    }
    KeyService keyService(events, *keyGateway, *userDirectoryGateway, *cryptoProvider, store, sessionService, config.deviceId);
    MessageService messageService(events, *messageGateway, *userDirectoryGateway, *cryptoProvider, store, sessionService, keyService, config.deviceId);
    ClientController controller(events, config, sessionService, keyService, messageService);
    CommandRouter router(events, controller);
    ConsolePresenter presenter(events, config.showRawErrors);
    ConsoleInputWorker inputWorker;

    QObject::connect(&inputWorker, &ConsoleInputWorker::lineRead, &router, &CommandRouter::handleLine, Qt::QueuedConnection);
    QObject::connect(&events, &EventBus::exitRequested, &app, &QCoreApplication::quit);

    inputWorker.start();
    const int result = app.exec();
    inputWorker.requestStop();
    return result;
}
