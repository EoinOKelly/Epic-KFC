#include "app/StartupConfig.h"
#include "app/SlashCommandParser.h"
#include "crypto/MockCryptoProvider.h"
#include "crypto/NativeSignalCryptoProvider.h"
#include "domain/Models.h"
#include "storage/JsonLocalStore.h"

#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>

#include <iostream>

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

void testParser() {
    SlashCommandParser parser;
    const auto login = parser.parse("/LOGIN alice@example.com");
    expect(login.succeeded() && login.value().type == CommandType::Login, "parser accepts case-insensitive slash command");

    const auto quoted = parser.parse("/download msg-1 \"C:/Temp/out file.txt\"");
    expect(quoted.succeeded() && quoted.value().arguments.at(1) == "C:/Temp/out file.txt", "parser handles quoted arguments");

    const auto rejected = parser.parse("login alice");
    expect(rejected.failed(), "parser rejects non-slash command");
}

void testStartupConfig() {
    StartupConfigParser parser;
    const auto mock = parser.parse({"client"});
    expect(mock.succeeded() && mock.value().mode == ClientMode::Mock, "startup defaults to mock mode");

    const auto real = parser.parse({"client", "--mode", "real", "--api-url", "https://example.test/api/v1", "--device-id", "2"});
    expect(real.succeeded() && real.value().mode == ClientMode::Real && real.value().deviceId == 2, "startup accepts real mode config");

    const auto invalid = parser.parse({"client", "--mode", "real"});
    expect(invalid.failed(), "startup rejects real mode without api url");

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

    const QJsonObject wire = QJsonDocument::fromJson(encrypted.value().wirePayloadJson.toUtf8()).object();
    expect(wire.contains("counter") && wire.contains("previousCounter") && wire.contains("ciphertext")
        && wire.contains("iv") && wire.contains("authTag"), "crypto emits required wire json fields");

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
        MessageDirection::Received
    };
    const auto decrypted = crypto.decrypt("bob", bob.value(), received, std::nullopt);
    expect(decrypted.succeeded() && decrypted.value() == "hello", "crypto decrypts first X3DH message");

    QJsonObject tampered = wire;
    tampered.insert("authTag", QString::fromLatin1(QByteArray("tampered-auth-tag").toBase64()));
    received.wirePayloadJson = QString::fromUtf8(QJsonDocument(tampered).toJson(QJsonDocument::Compact));
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
        MessageDirection::Received
    };
    const auto decrypted = crypto.decrypt("bob", bob.value(), received, std::nullopt);
    expect(decrypted.succeeded() && decrypted.value() == "mock hello", "mock crypto decrypts demo payloads");
}

void testEncryptedLocalStore() {
#if CLIENT_HAS_OPENSSL
    const QString stateFileName = "client-test-state.json";
    const QString path = QDir::current().filePath(stateFileName);
    QFile::remove(path);
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

    const auto savedSession = store.saveSession(session);
    const auto savedDevice = store.saveDeviceKeys(device);
    const auto savedPreKey = store.saveOneTimePreKeys({preKey});
    const auto savedTrustPin = store.saveTrustPin(trustPin);
    expect(savedSession.succeeded(), "encrypted store saves protected session");
    expect(savedDevice.succeeded(), "encrypted store saves protected device keys");
    expect(savedPreKey.succeeded(), "encrypted store saves protected one-time pre-keys");
    expect(savedTrustPin.succeeded(), "encrypted store saves protected trust pins");

    QFile file(path);
    file.open(QIODevice::ReadOnly);
    const QString rawState = QString::fromUtf8(file.readAll());
    file.close();
    const bool secretsHidden = !rawState.contains("access-secret-token")
        && !rawState.contains("refresh-secret-token")
        && !rawState.contains("identity-private-secret")
        && !rawState.contains("one-time-private-secret")
        && !rawState.contains("trusted-identity-secret");
    expect(secretsHidden, "encrypted store does not write secrets as plaintext");

    JsonLocalStore reloaded(path, true);
    reloaded.setSecretPassphrase(passphrase);
    const auto reloadResult = reloaded.reload();
    const auto loadedSession = reloaded.loadSession();
    const auto loadedDevice = reloaded.loadDeviceKeys(1);
    const auto loadedPreKeys = reloaded.loadOneTimePreKeys(1);
    const auto loadedTrustPin = reloaded.trustPin("bob", 1);
    const bool loaded = reloadResult.succeeded()
        && loadedSession.succeeded()
        && loadedSession.value().has_value()
        && loadedSession.value()->tokens.refreshToken == "refresh-secret-token"
        && loadedDevice.succeeded()
        && loadedDevice.value().has_value()
        && loadedDevice.value()->identityPrivateKey == "identity-private-secret"
        && loadedPreKeys.succeeded()
        && !loadedPreKeys.value().isEmpty()
        && loadedPreKeys.value().first().privateKey == "one-time-private-secret"
        && loadedTrustPin.succeeded()
        && loadedTrustPin.value().has_value()
        && loadedTrustPin.value()->identityKey == "trusted-identity-secret";
    expect(loaded, "encrypted store reloads secrets with passphrase");
    QFile::remove(path);
#else
    expect(true, "encrypted store test skipped without OpenSSL");
#endif
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

    return failures == 0 ? 0 : 1;
}
