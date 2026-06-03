#include "app/EventBus.h"
#include "app/StartupConfig.h"
#include "app/SlashCommandParser.h"
#include "crypto/MockCryptoProvider.h"
#include "crypto/NativeSignalCryptoProvider.h"
#include "domain/Models.h"
#include "gateways/Gateways.h"
#include "services/Services.h"
#include "storage/JsonLocalStore.h"
#include "support/ClientConstants.h"

#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>

#include <iostream>
#include <memory>

namespace {
int failures = 0;

void expect(bool condition, const char* name) {
    if (condition) {
        std::cout << "[PASS] " << name << '\n';
        return;
    }
    std::cout << "[FAIL] " << name << '\n';
    ++failures;
}

QJsonObject wireBodyFromEnvelope(const QString& wirePayloadJson) {
    const QJsonObject envelope = QJsonDocument::fromJson(wirePayloadJson.toUtf8()).object();
    const QByteArray body = QByteArray::fromBase64(envelope.value(CryptoText::WireBodyB64).toString().toLatin1());
    return QJsonDocument::fromJson(body).object();
}

class TestAuthGateway : public IAuthGateway {
public:
    void registerUser(const QString&, const QString&, const QString&, GatewayCallback<UserProfile> callback) override {
        callback(Result<UserProfile>::failure({ErrorCode::OperationFailed, "not used"}));
    }

    void login(const QString&, const QString&, GatewayCallback<AuthSession> callback) override {
        callback(Result<AuthSession>::failure({ErrorCode::OperationFailed, "not used"}));
    }

    void currentUser(const QString&, GatewayCallback<UserProfile> callback) override {
        callback(Result<UserProfile>::failure({ErrorCode::OperationFailed, "not used"}));
    }

    void logout(const QString&, GatewayCallback<bool> callback) override {
        callback(Result<bool>::success(true));
    }
};

class TestKeyGateway : public IKeyGateway {
public:
    void upsertDeviceKeys(const QString&, const DeviceKeyMaterial&, GatewayCallback<bool> callback) override {
        callback(Result<bool>::failure({ErrorCode::OperationFailed, "not used"}));
    }

    void uploadOneTimePreKeys(const QString&, int, const std::vector<OneTimePreKey>&, GatewayCallback<bool> callback) override {
        callback(Result<bool>::failure({ErrorCode::OperationFailed, "not used"}));
    }

    void fetchPreKeyBundle(const QString&, const QString&, int, GatewayCallback<PreKeyBundle> callback) override {
        callback(Result<PreKeyBundle>::failure({ErrorCode::OperationFailed, "not used"}));
    }
};

class TestUserDirectoryGateway : public IUserDirectoryGateway {
public:
    void resolveUsername(const QString&, const QString& username, int defaultDeviceId, GatewayCallback<UserAddress> callback) override {
        callback(Result<UserAddress>::success({username, username, defaultDeviceId}));
    }
};

class TestMessageGateway : public IMessageGateway {
public:
    Result<BlockchainAnchor> anchorResult = Result<BlockchainAnchor>::failure({ErrorCode::NotFound, "Anchor not found"});
    Result<BlockchainVerification> verificationResult = Result<BlockchainVerification>::failure({ErrorCode::OperationFailed, "not configured"});
    bool fetchCalled{false};
    bool verifyCalled{false};

    void sendMessage(const QString&, const LocalMessage&, std::optional<int>, GatewayCallback<LocalMessage> callback) override {
        callback(Result<LocalMessage>::failure({ErrorCode::OperationFailed, "not used"}));
    }

    void listReceived(const QString&, GatewayCallback<MessageList> callback) override {
        callback(Result<MessageList>::success({}));
    }

    void listSent(const QString&, GatewayCallback<MessageList> callback) override {
        callback(Result<MessageList>::success({}));
    }

    void getMessage(const QString&, const QString&, GatewayCallback<LocalMessage> callback) override {
        callback(Result<LocalMessage>::failure({ErrorCode::OperationFailed, "not used"}));
    }

    void forwardMessage(const QString&, const QString&, const LocalMessage&, std::optional<int>, GatewayCallback<LocalMessage> callback) override {
        callback(Result<LocalMessage>::failure({ErrorCode::OperationFailed, "not used"}));
    }

    void revokeMessage(const QString&, const QString&, GatewayCallback<LocalMessage> callback) override {
        callback(Result<LocalMessage>::failure({ErrorCode::OperationFailed, "not used"}));
    }

    void deleteMessage(const QString&, const QString&, GatewayCallback<bool> callback) override {
        callback(Result<bool>::failure({ErrorCode::OperationFailed, "not used"}));
    }

    void fetchMessageAnchor(const QString&, const QString&, GatewayCallback<BlockchainAnchor> callback) override {
        fetchCalled = true;
        callback(anchorResult);
    }

    void verifyAnchor(const QString&, const BlockchainAnchor&, GatewayCallback<BlockchainVerification> callback) override {
        verifyCalled = true;
        callback(verificationResult);
    }
};

struct VerificationFixture {
    QString statePath;
    EventBus events;
    TestAuthGateway authGateway;
    TestKeyGateway keyGateway;
    TestUserDirectoryGateway userDirectoryGateway;
    TestMessageGateway messageGateway;
    MockCryptoProvider cryptoProvider;
    JsonLocalStore store;
    SessionService sessionService;
    KeyService keyService;
    MessageService messageService;
    QString fidelityStatus;
    std::optional<ClientError> commandError;

    explicit VerificationFixture(QString path)
        : statePath(std::move(path))
        , store(statePath, false)
        , sessionService(events, authGateway, store, false)
        , keyService(events, keyGateway, userDirectoryGateway, cryptoProvider, store, sessionService, 1)
        , messageService(events, messageGateway, userDirectoryGateway, cryptoProvider, store, sessionService, keyService, 1) {
        QObject::connect(&events, &EventBus::fidelityStatusUpdated, &events, [this](const QString&, const QString& status) {
            fidelityStatus = status;
        });
        QObject::connect(&events, &EventBus::commandFailed, &events, [this](const ClientError& error) {
            commandError = error;
        });
    }
};

BlockchainAnchor testAnchor(const QString& status) {
    return {
        "anchor-1",
        "ccd07804-e033-4a7b-9ae9-24af64997c91",
        "0x0000000000000000000000000000000000000000000000000000000000000001",
        "0x1111111111111111111111111111111111111111111111111111111111111111",
        {},
        "0x2222222222222222222222222222222222222222222222222222222222222222",
        "0x3333333333333333333333333333333333333333",
        "sepolia",
        status,
        {}
    };
}

BlockchainVerification testVerification(bool valid) {
    return {
        valid,
        "sepolia",
        "confirmed",
        "anchor-1",
        "ccd07804-e033-4a7b-9ae9-24af64997c91",
        "0x0000000000000000000000000000000000000000000000000000000000000001",
        "0x1111111111111111111111111111111111111111111111111111111111111111",
        "0x2222222222222222222222222222222222222222222222222222222222222222",
        "0x3333333333333333333333333333333333333333",
        "2026-06-03T12:00:00Z"
    };
}

std::unique_ptr<VerificationFixture> createVerificationFixture(const QString& fileName, bool seedSession = true) {
    const QString path = QDir::current().filePath(fileName);
    QFile::remove(path);

    if (seedSession) {
        JsonLocalStore seed(path, false);
        const AuthSession session{
            {"user-1", "alice", "alice@example.test"},
            {"access-token", "refresh-token", "bearer", 3600}
        };
        seed.saveSession(session);
    }

    return std::make_unique<VerificationFixture>(path);
}

QString envelopeWithBody(const QString& wirePayloadJson, const QJsonObject& body) {
    QJsonObject envelope = QJsonDocument::fromJson(wirePayloadJson.toUtf8()).object();
    envelope.insert(CryptoText::WireBodyB64, QString::fromLatin1(QJsonDocument(body).toJson(QJsonDocument::Compact).toBase64()));
    return QString::fromUtf8(QJsonDocument(envelope).toJson(QJsonDocument::Compact));
}

void testParser() {
    SlashCommandParser parser;
    const auto login = parser.parse("/LOGIN alice@example.com");
    expect(login.succeeded() && login.value().type == CommandType::Login, "parser accepts case-insensitive slash command");

    const auto msg = parser.parse("/msg bob");
    expect(msg.succeeded() && msg.value().type == CommandType::Msg && msg.value().arguments.at(0) == "bob", "parser accepts IRC-style username message command");

    const auto back = parser.parse("/back");
    expect(back.succeeded() && back.value().type == CommandType::Back, "parser accepts back command");

    const auto quoted = parser.parse("/download msg-1 \"C:/Temp/out file.txt\"");
    expect(quoted.succeeded() && quoted.value().arguments.at(1) == "C:/Temp/out file.txt", "parser handles quoted arguments");

    const auto rejected = parser.parse("login alice");
    expect(rejected.failed(), "parser rejects non-slash command");
}

void testStartupConfig() {
    StartupConfigParser parser;
    const auto defaultReal = parser.parse({"client"});
    const bool defaultRealMode = defaultReal.succeeded()
        && defaultReal.value().mode == ClientMode::Real
        && defaultReal.value().apiUrl == AppText::DefaultApiUrl;
    expect(defaultRealMode, "startup defaults to real mode with team API URL");

    const auto debug = parser.parse({"client", "--debug"});
    expect(debug.succeeded()
        && debug.value().mode == ClientMode::Mock
        && debug.value().apiUrl.isEmpty()
        && debug.value().showRawErrors, "startup debug flag selects mock mode");

    const auto debugErrors = parser.parse({"client", "--debug-errors"});
    expect(debugErrors.succeeded()
        && debugErrors.value().mode == ClientMode::Real
        && debugErrors.value().showRawErrors, "startup debug errors flag enables raw error output");

    const auto real = parser.parse({"client", "--mode", "real", "--api-url", "https://example.test/api/v1", "--device-id", "2"});
    expect(real.succeeded() && real.value().mode == ClientMode::Real && real.value().deviceId == 2, "startup accepts real mode config");

    const auto realDefaultUrl = parser.parse({"client", "--mode", "real"});
    expect(realDefaultUrl.succeeded() && realDefaultUrl.value().apiUrl == AppText::DefaultApiUrl, "startup real mode uses default API URL");

    const auto debugRealConflict = parser.parse({"client", "--debug", "--mode", "real"});
    expect(debugRealConflict.failed(), "startup rejects debug with real mode");

    const auto realDebugConflict = parser.parse({"client", "--mode", "real", "--debug"});
    expect(realDebugConflict.failed(), "startup rejects real mode with debug");

    const auto debugApiConflict = parser.parse({"client", "--debug", "--api-url", "https://example.test/api/v1"});
    expect(debugApiConflict.failed(), "startup rejects debug with API URL");

    const auto insecure = parser.parse({"client", "--mode", "real", "--api-url", "http://localhost:8000/api/v1"});
    expect(insecure.failed(), "startup rejects real mode without HTTPS");
}

void testCryptoWireShape() {
    NativeSignalCryptoProvider crypto;
#if CLIENT_HAS_OPENSSL
    const auto alice = crypto.loadOrCreateDevice({}, 1);
    const auto bob = crypto.loadOrCreateDevice({}, 1);
    expect(alice.succeeded() && bob.succeeded(), "crypto creates device key material");

    PreKeyBundle bundle{
        "bob",
        bob.value().registrationId,
        bob.value().deviceId,
        bob.value().identityKey,
        bob.value().identitySigningKey,
        bob.value().signedPreKeyId,
        bob.value().signedPreKey,
        bob.value().signedPreKeySignature,
        std::nullopt,
        {}
    };

    const auto verified = crypto.verifySignedPreKey(bundle);
    expect(verified.succeeded(), "crypto validates pre-key bundle shape");

    const auto encrypted = crypto.encrypt("alice", alice.value(), bundle, "hello");
    expect(encrypted.succeeded(), "crypto encrypts message");
    expect(!encrypted.value().consumedOneTimePreKeyId.has_value(), "crypto leaves one-time pre-key unconsumed");

    const QJsonObject envelope = QJsonDocument::fromJson(encrypted.value().wirePayloadJson.toUtf8()).object();
    const QJsonObject wire = wireBodyFromEnvelope(encrypted.value().wirePayloadJson);
    const bool hasEnvelope = envelope.value(CryptoText::WireFormat).toString() == CryptoText::WireFormatValue
        && envelope.value(CryptoText::WireType).toInt() == CryptoText::WirePreKeyWhisperMessageType
        && !envelope.value(CryptoText::WireBodyB64).toString().isEmpty();
    const bool hasBody = wire.contains("counter") && wire.contains("previousCounter") && wire.contains("ciphertext")
        && wire.contains("iv") && wire.contains("authTag");
    expect(hasEnvelope && hasBody, "crypto emits required wire json fields");

    LocalMessage received{
        "message-1",
        "alice",
        alice.value().deviceId,
        "bob",
        bob.value().deviceId,
        encrypted.value().wirePayloadJson,
        encrypted.value().consumedOneTimePreKeyId,
        QDateTime::currentDateTimeUtc(),
        {},
        {},
        {},
        {},
        {},
        {},
        MessageDirection::Received
    };
    const auto decrypted = crypto.decrypt("bob", bob.value(), received, std::nullopt);
    expect(decrypted.succeeded() && decrypted.value() == "hello", "crypto decrypts first X3DH message");

    const auto secondEncrypted = crypto.encrypt("alice", alice.value(), bundle, "second hello");
    const QJsonObject secondEnvelope = secondEncrypted.succeeded()
        ? QJsonDocument::fromJson(secondEncrypted.value().wirePayloadJson.toUtf8()).object()
        : QJsonObject{};
    const QJsonObject secondWire = secondEncrypted.succeeded()
        ? wireBodyFromEnvelope(secondEncrypted.value().wirePayloadJson)
        : QJsonObject{};
    LocalMessage secondReceived{
        "message-1b",
        "alice",
        alice.value().deviceId,
        "bob",
        bob.value().deviceId,
        secondEncrypted.succeeded() ? secondEncrypted.value().wirePayloadJson : QString{},
        secondEncrypted.succeeded() ? secondEncrypted.value().consumedOneTimePreKeyId : std::nullopt,
        QDateTime::currentDateTimeUtc(),
        {},
        {},
        {},
        {},
        {},
        {},
        MessageDirection::Received
    };
    const auto secondDecrypted = secondEncrypted.succeeded()
        ? crypto.decrypt("bob", bob.value(), secondReceived, std::nullopt)
        : Result<QString>::failure({ErrorCode::CryptoError, "Second encryption failed."});
    const bool secondMessageUsesPreKeyEnvelope = secondEnvelope.value(CryptoText::WireType).toInt() == CryptoText::WirePreKeyWhisperMessageType
        && secondWire.value(CryptoText::WireX3dh).isObject();
    expect(secondMessageUsesPreKeyEnvelope && secondDecrypted.succeeded() && secondDecrypted.value() == "second hello", "crypto decrypts second message without persisted ratchet state");

    PreKeyBundle selfBundle{
        "alice",
        alice.value().registrationId,
        alice.value().deviceId,
        alice.value().identityKey,
        alice.value().identitySigningKey,
        alice.value().signedPreKeyId,
        alice.value().signedPreKey,
        alice.value().signedPreKeySignature,
        std::nullopt,
        {}
    };
    const auto selfEncrypted = crypto.encrypt("alice", alice.value(), selfBundle, "local sender copy");
    LocalMessage selfCopy{
        "message-2",
        "alice",
        alice.value().deviceId,
        "bob",
        bob.value().deviceId,
        selfEncrypted.succeeded() ? selfEncrypted.value().wirePayloadJson : QString{},
        std::nullopt,
        QDateTime::currentDateTimeUtc(),
        {},
        {},
        {},
        {},
        {},
        {},
        MessageDirection::Sent
    };
    const auto selfDecrypted = selfEncrypted.succeeded()
        ? crypto.decrypt("alice", alice.value(), selfCopy, std::nullopt)
        : Result<QString>::failure({ErrorCode::CryptoError, "Self encryption failed."});
    expect(selfDecrypted.succeeded() && selfDecrypted.value() == "local sender copy", "crypto decrypts local sender copy");

    if (selfEncrypted.succeeded()) {
        QJsonObject tamperedSelf = wireBodyFromEnvelope(selfEncrypted.value().wirePayloadJson);
        tamperedSelf.insert("authTag", QString::fromLatin1(QByteArray("tampered-auth-tag").toBase64()));
        selfCopy.wirePayloadJson = envelopeWithBody(selfEncrypted.value().wirePayloadJson, tamperedSelf);
        const auto rejectedSelf = crypto.decrypt("alice", alice.value(), selfCopy, std::nullopt);
        expect(rejectedSelf.failed(), "crypto rejects tampered local sender copy");
    } else {
        expect(false, "crypto rejects tampered local sender copy");
    }

    QJsonObject tampered = wire;
    tampered.insert("authTag", QString::fromLatin1(QByteArray("tampered-auth-tag").toBase64()));
    received.wirePayloadJson = envelopeWithBody(encrypted.value().wirePayloadJson, tampered);
    const auto rejected = crypto.decrypt("bob", bob.value(), received, std::nullopt);
    expect(rejected.failed(), "crypto rejects tampered AES-GCM payload");
#else
    expect(!crypto.isAvailable(), "native crypto reports unavailable without OpenSSL");
#endif
}

void testMockCrypto() {
    MockCryptoProvider crypto;
    const auto alice = crypto.loadOrCreateDevice({}, 1);
    const auto bob = crypto.loadOrCreateDevice({}, 1);
    expect(alice.succeeded() && bob.succeeded(), "mock crypto creates device key material");

    PreKeyBundle bundle{
        "bob",
        bob.value().registrationId,
        bob.value().deviceId,
        bob.value().identityKey,
        bob.value().identitySigningKey,
        bob.value().signedPreKeyId,
        bob.value().signedPreKey,
        bob.value().signedPreKeySignature,
        std::nullopt,
        {}
    };

    const auto encrypted = crypto.encrypt("alice", alice.value(), bundle, "mock hello");
    LocalMessage received{
        "message-1",
        "alice",
        alice.value().deviceId,
        "bob",
        bob.value().deviceId,
        encrypted.value().wirePayloadJson,
        encrypted.value().consumedOneTimePreKeyId,
        QDateTime::currentDateTimeUtc(),
        {},
        {},
        {},
        {},
        {},
        {},
        MessageDirection::Received
    };
    const auto decrypted = crypto.decrypt("bob", bob.value(), received, std::nullopt);
    expect(decrypted.succeeded() && decrypted.value() == "mock hello", "mock crypto decrypts demo payloads");
}

void testEncryptedLocalStore() {
#if CLIENT_HAS_OPENSSL
    const QString stateFileName = "client-test-state.json";
    const QString path = QDir::current().filePath(stateFileName);
    const QString accountPath = QDir::current().filePath("user_2-client-state.json");
    QFile::remove(path);
    QFile::remove(accountPath);
    const QString passphrase = "local-test-passphrase";
    JsonLocalStore store(path, true);
    store.setSecretPassphrase(passphrase);

    const AuthSession session{
        {"user-1", "alice", "alice@example.test"},
        {"access-secret-token", "refresh-secret-token", "bearer", 3600}
    };
    const DeviceKeyMaterial device{
        1,
        12345,
        "identity-public",
        "identity-private-secret",
        "signing-public",
        "signing-private-secret",
        1,
        "signed-pre-key-public",
        "signed-pre-key-private-secret",
        "signed-pre-key-signature"
    };
    const OneTimePreKey preKey{1, 7, "one-time-public", "one-time-private-secret", false};
    const TrustPin trustPin{"bob", 1, "trusted-identity-secret", QDateTime::currentDateTimeUtc()};
    const UserAddress bobAddress{"bob", "bobUsername", 1};
    const LocalMessage message{
        "stored-message-1",
        "bob",
        1,
        "user-1",
        1,
        "{}",
        std::nullopt,
        QDateTime::currentDateTimeUtc(),
        {},
        {},
        {},
        {},
        {},
        "encrypted-local-sender-copy",
        MessageDirection::Received
    };

    const auto savedSession = store.saveSession(session);
    const auto savedDevice = store.saveDeviceKeys(device);
    const auto savedPreKey = store.saveOneTimePreKeys({preKey});
    const auto savedKnownUser = store.saveKnownUser(bobAddress);
    const auto savedTrustPin = store.saveTrustPin(trustPin);
    const auto savedMessage = store.saveMessage(message);
    expect(savedSession.succeeded(), "encrypted store saves protected session");
    expect(savedDevice.succeeded(), "encrypted store saves protected device keys");
    expect(savedPreKey.succeeded(), "encrypted store saves protected one-time pre-keys");
    expect(savedKnownUser.succeeded(), "encrypted store saves known usernames");
    expect(savedTrustPin.succeeded(), "encrypted store saves protected trust pins");
    expect(savedMessage.succeeded(), "encrypted store saves cached messages");

    QFile file(path);
    file.open(QIODevice::ReadOnly);
    const QString rawState = QString::fromUtf8(file.readAll());
    file.close();
    const bool secretsHidden = !rawState.contains("access-secret-token")
        && !rawState.contains("refresh-secret-token")
        && !rawState.contains("identity-private-secret")
        && !rawState.contains("one-time-private-secret")
        && !rawState.contains("trusted-identity-secret")
        && !rawState.contains("locally cached sent body");
    expect(secretsHidden, "encrypted store does not write secrets as plaintext");

    JsonLocalStore reloaded(path, true);
    reloaded.setSecretPassphrase(passphrase);
    const auto reloadResult = reloaded.reload();
    const auto loadedSession = reloaded.loadSession();
    const auto loadedDevice = reloaded.loadDeviceKeys(1);
    const auto loadedPreKeys = reloaded.loadOneTimePreKeys(1);
    const auto loadedKnownUser = reloaded.knownUser("bob", 1);
    const auto loadedTrustPin = reloaded.trustPin("bob", 1);
    const auto loadedMessage = reloaded.findMessage("stored-message-1");
    const auto conversations = reloaded.conversationsFor("user-1");
    const bool loaded = reloadResult.succeeded()
        && loadedSession.succeeded()
        && loadedSession.value().has_value()
        && loadedSession.value()->tokens.refreshToken == "refresh-secret-token"
        && loadedDevice.succeeded()
        && loadedDevice.value().has_value()
        && loadedDevice.value()->identityPrivateKey == "identity-private-secret"
        && loadedPreKeys.succeeded()
        && !loadedPreKeys.value().empty()
        && loadedPreKeys.value().front().privateKey == "one-time-private-secret"
        && loadedKnownUser.succeeded()
        && loadedKnownUser.value().has_value()
        && loadedKnownUser.value()->username == "bobUsername"
        && loadedTrustPin.succeeded()
        && loadedTrustPin.value().has_value()
        && loadedTrustPin.value()->identityKey == "trusted-identity-secret"
        && loadedMessage.succeeded()
        && loadedMessage.value().has_value()
        && loadedMessage.value()->localSenderCopyWirePayloadJson == "encrypted-local-sender-copy"
        && conversations.succeeded()
        && !conversations.value().empty()
        && conversations.value().front().peerUsername == "bobUsername";
    expect(loaded, "encrypted store reloads secrets with passphrase");

    JsonLocalStore accountScoped(path, true);
    accountScoped.setSecretPassphrase("different-account-passphrase");
    accountScoped.useAccountScopedPath("user/2");
    const AuthSession accountSession{
        {"user/2", "bob", "bob@example.test"},
        {"account-token", "account-refresh", "bearer", 3600}
    };
    const auto savedAccountSession = accountScoped.saveSession(accountSession);
    const auto accountStateIsSeparate = QFile::exists(accountPath);
    JsonLocalStore accountIndex(path, true);
    const auto lastAccount = accountIndex.lastAccountId();
    const bool accountIndexSaved = lastAccount.succeeded()
        && lastAccount.value().has_value()
        && *lastAccount.value() == "user/2";
    expect(savedAccountSession.succeeded() && accountStateIsSeparate && accountIndexSaved, "encrypted store scopes default state by account");

    QFile::remove(path);
    QFile::remove(accountPath);
#else
    expect(true, "encrypted store test skipped without OpenSSL");
#endif
}

void testBlockchainVerificationFlow() {
    const QString messageId = "ccd07804-e033-4a7b-9ae9-24af64997c91";

    {
        auto fixture = createVerificationFixture("client-test-verify-pending.json");
        fixture->messageGateway.anchorResult = Result<BlockchainAnchor>::success(testAnchor("pending"));
        fixture->messageService.verify(messageId);
        const bool pendingReported = fixture->messageGateway.fetchCalled
            && !fixture->messageGateway.verifyCalled
            && fixture->fidelityStatus.contains("pending", Qt::CaseInsensitive);
        expect(pendingReported, "verify reports pending anchors without backend verification call");
        QFile::remove(fixture->statePath);
    }

    {
        auto fixture = createVerificationFixture("client-test-verify-logged-out.json", false);
        fixture->messageGateway.anchorResult = Result<BlockchainAnchor>::success(testAnchor("pending"));
        fixture->messageService.verify(messageId);
        const bool loggedOutVerifyAllowed = fixture->messageGateway.fetchCalled
            && !fixture->messageGateway.verifyCalled
            && !fixture->commandError.has_value()
            && fixture->fidelityStatus.contains("pending", Qt::CaseInsensitive);
        expect(loggedOutVerifyAllowed, "verify works without a logged-in session");
        QFile::remove(fixture->statePath);
    }

    {
        auto fixture = createVerificationFixture("client-test-verify-confirmed.json");
        fixture->messageGateway.anchorResult = Result<BlockchainAnchor>::success(testAnchor("confirmed"));
        fixture->messageGateway.verificationResult = Result<BlockchainVerification>::success(testVerification(true));
        fixture->messageService.verify(messageId);
        const bool confirmedVerified = fixture->messageGateway.fetchCalled
            && fixture->messageGateway.verifyCalled
            && fixture->fidelityStatus.contains("verified", Qt::CaseInsensitive)
            && fixture->fidelityStatus.contains("0x2222", Qt::CaseInsensitive);
        expect(confirmedVerified, "verify checks confirmed anchors through blockchain endpoint");
        QFile::remove(fixture->statePath);
    }

    {
        auto fixture = createVerificationFixture("client-test-verify-invalid-transaction.json");
        BlockchainAnchor anchor = testAnchor("confirmed");
        anchor.transactionHash = "not-a-transaction";
        fixture->messageGateway.anchorResult = Result<BlockchainAnchor>::success(anchor);
        fixture->messageService.verify(messageId);
        const bool invalidTransactionWaits = fixture->messageGateway.fetchCalled
            && !fixture->messageGateway.verifyCalled
            && fixture->fidelityStatus.contains("pending", Qt::CaseInsensitive);
        expect(invalidTransactionWaits, "verify waits when anchor transaction hash is invalid");
        QFile::remove(fixture->statePath);
    }

    {
        auto fixture = createVerificationFixture("client-test-verify-mismatch.json");
        fixture->messageGateway.anchorResult = Result<BlockchainAnchor>::success(testAnchor("confirmed"));
        fixture->messageGateway.verificationResult = Result<BlockchainVerification>::success(testVerification(false));
        fixture->messageService.verify(messageId);
        const bool mismatchReported = fixture->messageGateway.verifyCalled
            && fixture->fidelityStatus.contains("failed", Qt::CaseInsensitive);
        expect(mismatchReported, "verify reports confirmed anchor mismatches");
        QFile::remove(fixture->statePath);
    }

    {
        auto fixture = createVerificationFixture("client-test-verify-missing.json");
        fixture->messageGateway.anchorResult = Result<BlockchainAnchor>::failure({ErrorCode::NotFound, "Anchor not found"});
        fixture->messageService.verify(messageId);
        const bool missingReported = fixture->messageGateway.fetchCalled
            && !fixture->messageGateway.verifyCalled
            && fixture->fidelityStatus.contains("No blockchain anchor", Qt::CaseInsensitive);
        expect(missingReported, "verify reports missing anchors clearly");
        QFile::remove(fixture->statePath);
    }
}
}

int main(int argc, char* argv[]) {
    QCoreApplication app(argc, argv);
    registerClientMetaTypes();

    testParser();
    testStartupConfig();
    testCryptoWireShape();
    testMockCrypto();
    testEncryptedLocalStore();
    testBlockchainVerificationFlow();

    return failures == 0 ? 0 : 1;
}
