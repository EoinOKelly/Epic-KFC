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
#include <QTextStream>

#include <memory>

int main(int argc, char* argv[]) {
    QCoreApplication app(argc, argv);
    QCoreApplication::setApplicationName(AppText::ApplicationName);
    QCoreApplication::setOrganizationName(AppText::OrganizationName);
    registerClientMetaTypes();

    StartupConfigParser configParser;
    const auto parsedConfig = configParser.parse(QCoreApplication::arguments());
    if (parsedConfig.failed()) {
        QTextStream(stderr) << parsedConfig.error().message << '\n';
        return 1;
    }
    const StartupConfig config = parsedConfig.value();

    EventBus events;
    JsonLocalStore store(config.statePath);
    std::unique_ptr<ICryptoProvider> cryptoProvider;
    std::unique_ptr<HttpClient> httpClient;
    std::unique_ptr<IAuthGateway> httpAuthGateway;
    std::unique_ptr<IKeyGateway> httpKeyGateway;
    std::unique_ptr<IMessageGateway> httpMessageGateway;
    std::unique_ptr<IAuthGateway> mockAuthGateway;
    std::unique_ptr<IKeyGateway> mockKeyGateway;
    std::unique_ptr<IMessageGateway> mockMessageGateway;

    IAuthGateway* authGateway = nullptr;
    IKeyGateway* keyGateway = nullptr;
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
        httpMessageGateway = std::make_unique<HttpMessageGateway>(*httpClient);
        authGateway = httpAuthGateway.get();
        keyGateway = httpKeyGateway.get();
        messageGateway = httpMessageGateway.get();
    } else {
        cryptoProvider = std::make_unique<MockCryptoProvider>();
        mockAuthGateway = std::make_unique<MockAuthGateway>();
        mockKeyGateway = std::make_unique<MockKeyGateway>();
        mockMessageGateway = std::make_unique<MockMessageGateway>();
        authGateway = mockAuthGateway.get();
        keyGateway = mockKeyGateway.get();
        messageGateway = mockMessageGateway.get();
    }

    SessionService sessionService(events, *authGateway, store);
    KeyService keyService(events, *keyGateway, *cryptoProvider, store, sessionService, config.deviceId);
    MessageService messageService(events, *messageGateway, *cryptoProvider, store, sessionService, keyService, config.deviceId);
    ClientController controller(events, config, sessionService, keyService, messageService);
    CommandRouter router(events, controller);
    ConsolePresenter presenter(events);
    ConsoleInputWorker inputWorker;

    QObject::connect(&inputWorker, &ConsoleInputWorker::lineRead, &router, &CommandRouter::handleLine);
    QObject::connect(&events, &EventBus::exitRequested, &app, &QCoreApplication::quit);

    inputWorker.start();
    const int result = app.exec();
    inputWorker.requestStop();
    return result;
}
