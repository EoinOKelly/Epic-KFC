#include "app/StartupConfig.h"
#include "app/SlashCommandParser.h"
#include "crypto/MockCryptoProvider.h"
#include "crypto/NativeSignalCryptoProvider.h"
#include "domain/Models.h"

#include <QCoreApplication>
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
}

int main(int argc, char* argv[]) {
    QCoreApplication app(argc, argv);
    registerClientMetaTypes();

    testParser();
    testStartupConfig();
    testCryptoWireShape();
    testMockCrypto();

    return failures == 0 ? 0 : 1;
}
