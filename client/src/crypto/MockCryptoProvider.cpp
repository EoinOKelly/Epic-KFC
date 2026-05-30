#include "crypto/MockCryptoProvider.h"

#include "support/ClientConstants.h"

#include <QJsonDocument>
#include <QJsonObject>

Result<DeviceKeyMaterial> MockCryptoProvider::loadOrCreateDevice(DeviceKeyMaterial existing, int deviceId) {
    if (!existing.identityKey.isEmpty()) {
        return Result<DeviceKeyMaterial>::success(existing);
    }

    const QString deviceLabel = QString("mock-device-%1").arg(deviceId);
    return Result<DeviceKeyMaterial>::success({
        deviceId,
        CryptoText::DefaultRegistrationIdMinimum + deviceId,
        encodedMockBytes(deviceLabel + "-identity-public"),
        encodedMockBytes(deviceLabel + "-identity-private"),
        encodedMockBytes(deviceLabel + "-signing-public"),
        encodedMockBytes(deviceLabel + "-signing-private"),
        CryptoText::SignedPreKeyId,
        encodedMockBytes(deviceLabel + "-signed-pre-key-public"),
        encodedMockBytes(deviceLabel + "-signed-pre-key-private"),
        encodedMockBytes(deviceLabel + "-signed-pre-key-signature")
    });
}

Result<std::vector<OneTimePreKey>> MockCryptoProvider::createOneTimePreKeys(int deviceId, int count) {
    std::vector<OneTimePreKey> preKeys;
    for (int index = 0; index < count; ++index) {
        const int preKeyId = CryptoText::FirstPreKeyId + index;
        const QString label = QString("mock-device-%1-pre-key-%2").arg(deviceId).arg(preKeyId);
        preKeys.push_back({
            deviceId,
            preKeyId,
            encodedMockBytes(label + "-public"),
            encodedMockBytes(label + "-private"),
            false
        });
    }
    return Result<std::vector<OneTimePreKey>>::success(preKeys);
}

Result<bool> MockCryptoProvider::verifySignedPreKey(const PreKeyBundle& bundle) {
    const bool hasRequiredFields = !bundle.identityKey.isEmpty()
        && !bundle.identitySigningKey.isEmpty()
        && !bundle.signedPreKey.isEmpty()
        && !bundle.signedPreKeySignature.isEmpty();
    if (!hasRequiredFields) {
        return Result<bool>::failure({ErrorCode::CryptoError, "Mock pre-key bundle is missing required fields."});
    }
    return Result<bool>::success(true);
}

Result<EncryptedPayload> MockCryptoProvider::encrypt(
    const QString& senderUserId,
    const DeviceKeyMaterial& senderDevice,
    const PreKeyBundle& recipientBundle,
    const QString& plaintext) {
    if (plaintext.trimmed().isEmpty()) {
        return Result<EncryptedPayload>::failure({ErrorCode::CryptoError, AppText::EmptyMessage});
    }

    const int counter = nextCounter(recipientBundle.userId, recipientBundle.deviceId);
    const QByteArray ciphertext = plaintext.toUtf8().toBase64();
    QJsonObject root{
        {CryptoText::WireCounter, counter},
        {CryptoText::WirePreviousCounter, 0},
        {CryptoText::WireCiphertext, QString::fromLatin1(ciphertext)},
        {CryptoText::WireIv, encodedMockBytes("mock-iv")},
        {CryptoText::WireAuthTag, encodedMockBytes("mock-auth-tag")},
        {CryptoText::WireRatchetPublicKey, senderDevice.signedPreKey}
    };

    if (counter == 0) {
        root.insert(CryptoText::WireX3dh, QJsonObject{
            {CryptoText::WireIdentityKey, senderDevice.identityKey},
            {CryptoText::WireEphemeralKey, encodedMockBytes(QString("mock-ephemeral-%1").arg(senderUserId))}
        });
    }

    return Result<EncryptedPayload>::success({
        QString::fromUtf8(QJsonDocument(root).toJson(QJsonDocument::Compact)),
        recipientBundle.oneTimePreKeyId
    });
}

Result<QString> MockCryptoProvider::decrypt(
    const QString& currentUserId,
    const DeviceKeyMaterial& currentDevice,
    const LocalMessage& message,
    const std::optional<OneTimePreKey>& oneTimePreKey) {
    Q_UNUSED(currentUserId)
    Q_UNUSED(currentDevice)
    Q_UNUSED(oneTimePreKey)

    const QJsonObject root = QJsonDocument::fromJson(message.wirePayloadJson.toUtf8()).object();
    const QString encodedCiphertext = root.value(CryptoText::WireCiphertext).toString();
    const QByteArray plaintext = QByteArray::fromBase64(encodedCiphertext.toLatin1());
    if (plaintext.isEmpty() && !encodedCiphertext.isEmpty()) {
        return Result<QString>::failure({ErrorCode::CryptoError, "Mock payload could not be decoded."});
    }
    return Result<QString>::success(QString::fromUtf8(plaintext));
}

QString MockCryptoProvider::encodedMockBytes(const QString& label) const {
    QByteArray bytes = label.toUtf8();
    while (bytes.size() < CryptoText::KeyBytes) {
        bytes.append('-');
        bytes.append(label.toUtf8());
    }
    bytes.truncate(CryptoText::KeyBytes);
    return toBase64(bytes);
}

QString MockCryptoProvider::toBase64(const QByteArray& value) const {
    return QString::fromLatin1(value.toBase64());
}

int MockCryptoProvider::nextCounter(const QString& userId, int deviceId) {
    const QString key = QString("%1:%2").arg(userId).arg(deviceId);
    const auto foundCounter = m_sendCounters.find(key);
    const int counter = foundCounter == m_sendCounters.end() ? 0 : foundCounter->second;
    m_sendCounters.insert_or_assign(key, counter + 1);
    return counter;
}
