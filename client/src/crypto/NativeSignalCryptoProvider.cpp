#include "crypto/NativeSignalCryptoProvider.h"

#include "support/ClientConstants.h"

#include <QCryptographicHash>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMessageAuthenticationCode>
#include <QRandomGenerator>

namespace {
QByteArray intToBigEndian(int value) {
    QByteArray bytes(4, Qt::Uninitialized);
    bytes[0] = static_cast<char>((value >> 24) & 0xff);
    bytes[1] = static_cast<char>((value >> 16) & 0xff);
    bytes[2] = static_cast<char>((value >> 8) & 0xff);
    bytes[3] = static_cast<char>(value & 0xff);
    return bytes;
}

bool isValidBase64(const QString& value) {
    return !value.isEmpty() && !QByteArray::fromBase64(value.toLatin1()).isEmpty();
}
}

Result<DeviceKeyMaterial> NativeSignalCryptoProvider::loadOrCreateDevice(DeviceKeyMaterial existing, int deviceId) {
    if (!existing.identityKey.isEmpty()) {
        return Result<DeviceKeyMaterial>::success(existing);
    }

    const QByteArray identityPrivate = randomBytes(CryptoText::KeyBytes);
    const QByteArray signingPrivate = randomBytes(CryptoText::KeyBytes);
    const QByteArray signedPreKeyPrivate = randomBytes(CryptoText::KeyBytes);
    const QByteArray identityPublic = identityPrivate;
    const QByteArray signingPublic = signingPrivate;
    const QByteArray signedPreKeyPublic = signedPreKeyPrivate;
    const QByteArray signature = hmac(signingPublic, signedPreKeyPublic);
    const int registrationId = CryptoText::DefaultRegistrationIdMinimum
        + static_cast<int>(QRandomGenerator::global()->bounded(CryptoText::DefaultRegistrationIdRange));

    return Result<DeviceKeyMaterial>::success({
        deviceId,
        registrationId,
        toBase64(identityPublic),
        toBase64(identityPrivate),
        toBase64(signingPublic),
        toBase64(signingPrivate),
        CryptoText::SignedPreKeyId,
        toBase64(signedPreKeyPublic),
        toBase64(signedPreKeyPrivate),
        toBase64(signature)
    });
}

Result<QList<OneTimePreKey>> NativeSignalCryptoProvider::createOneTimePreKeys(int deviceId, int count) {
    QList<OneTimePreKey> preKeys;
    for (int index = 0; index < count; ++index) {
        const QByteArray privateKey = randomBytes(CryptoText::KeyBytes);
        preKeys.push_back({
            deviceId,
            CryptoText::FirstPreKeyId + index,
            toBase64(privateKey),
            toBase64(privateKey),
            false
        });
    }
    return Result<QList<OneTimePreKey>>::success(preKeys);
}

Result<bool> NativeSignalCryptoProvider::verifySignedPreKey(const PreKeyBundle& bundle) {
    const bool hasRequiredFields = isValidBase64(bundle.identityKey)
        && isValidBase64(bundle.identitySigningKey)
        && isValidBase64(bundle.signedPreKey)
        && isValidBase64(bundle.signedPreKeySignature);
    if (!hasRequiredFields) {
        return Result<bool>::failure({ErrorCode::CryptoError, "Pre-key bundle contains invalid base64 fields."});
    }
    return Result<bool>::success(true);
}

Result<EncryptedPayload> NativeSignalCryptoProvider::encrypt(
    const QString& senderUserId,
    const DeviceKeyMaterial& senderDevice,
    const PreKeyBundle& recipientBundle,
    const QString& plaintext) {
    if (plaintext.trimmed().isEmpty()) {
        return Result<EncryptedPayload>::failure({ErrorCode::CryptoError, AppText::EmptyMessage});
    }

    const int counter = nextCounter(recipientBundle.userId, recipientBundle.deviceId);
    const int previousCounter = 0;
    const QByteArray ratchetPublicKey = fromBase64(senderDevice.signedPreKey);
    const QByteArray iv = randomBytes(CryptoText::IvBytes);
    const QByteArray key = deriveMessageKey(
        fromBase64(senderDevice.identityPrivateKey),
        fromBase64(recipientBundle.identityKey),
        QByteArray(CryptoText::X3dhInfo.toUtf8()));
    const QByteArray aad = aadFor(counter, previousCounter, ratchetPublicKey);
    const QByteArray ciphertext = cryptWithKeystream(plaintext.toUtf8(), key, iv);
    const QByteArray tag = hmac(key, aad + ciphertext).left(CryptoText::AuthTagBytes);

    QJsonObject root{
        {CryptoText::WireCounter, counter},
        {CryptoText::WirePreviousCounter, previousCounter},
        {CryptoText::WireCiphertext, toBase64(ciphertext)},
        {CryptoText::WireIv, toBase64(iv)},
        {CryptoText::WireAuthTag, toBase64(tag)},
        {CryptoText::WireRatchetPublicKey, toBase64(ratchetPublicKey)}
    };

    if (counter == 0) {
        const QByteArray ephemeral = randomBytes(CryptoText::KeyBytes);
        root.insert(CryptoText::WireX3dh, QJsonObject{
            {CryptoText::WireIdentityKey, senderDevice.identityKey},
            {CryptoText::WireEphemeralKey, toBase64(ephemeral)}
        });
    }

    return Result<EncryptedPayload>::success({
        QString::fromUtf8(QJsonDocument(root).toJson(QJsonDocument::Compact)),
        recipientBundle.oneTimePreKeyId
    });
}

Result<QString> NativeSignalCryptoProvider::decrypt(const QString& currentUserId, const DeviceKeyMaterial& currentDevice, const LocalMessage& message) {
    Q_UNUSED(currentUserId)
    const QJsonObject root = QJsonDocument::fromJson(message.wirePayloadJson.toUtf8()).object();
    const int counter = root.value(CryptoText::WireCounter).toInt();
    const int previousCounter = root.value(CryptoText::WirePreviousCounter).toInt();
    const QByteArray ratchetPublicKey = fromBase64(root.value(CryptoText::WireRatchetPublicKey).toString());
    QByteArray remoteIdentityKey = ratchetPublicKey;

    const QJsonObject x3dh = root.value(CryptoText::WireX3dh).toObject();
    if (x3dh.contains(CryptoText::WireIdentityKey)) {
        remoteIdentityKey = fromBase64(x3dh.value(CryptoText::WireIdentityKey).toString());
    }

    const QByteArray iv = fromBase64(root.value(CryptoText::WireIv).toString());
    const QByteArray ciphertext = fromBase64(root.value(CryptoText::WireCiphertext).toString());
    const QByteArray receivedTag = fromBase64(root.value(CryptoText::WireAuthTag).toString());
    const QByteArray key = deriveMessageKey(
        fromBase64(currentDevice.identityPrivateKey),
        remoteIdentityKey,
        QByteArray(CryptoText::X3dhInfo.toUtf8()));
    const QByteArray aad = aadFor(counter, previousCounter, ratchetPublicKey);
    const QByteArray expectedTag = hmac(key, aad + ciphertext).left(CryptoText::AuthTagBytes);
    if (receivedTag != expectedTag) {
        return Result<QString>::failure({ErrorCode::CryptoError, "Message authentication failed."});
    }

    const QByteArray plaintext = cryptWithKeystream(ciphertext, key, iv);
    return Result<QString>::success(QString::fromUtf8(plaintext));
}

QByteArray NativeSignalCryptoProvider::randomBytes(qsizetype size) const {
    QByteArray bytes(size, Qt::Uninitialized);
    for (qsizetype index = 0; index < size; ++index) {
        bytes[index] = static_cast<char>(QRandomGenerator::system()->bounded(256));
    }
    return bytes;
}

QByteArray NativeSignalCryptoProvider::fromBase64(const QString& value) const {
    return QByteArray::fromBase64(value.toLatin1());
}

QString NativeSignalCryptoProvider::toBase64(const QByteArray& value) const {
    return QString::fromLatin1(value.toBase64());
}

QByteArray NativeSignalCryptoProvider::digest(const QByteArray& value) const {
    return QCryptographicHash::hash(value, QCryptographicHash::Sha256);
}

QByteArray NativeSignalCryptoProvider::hmac(const QByteArray& key, const QByteArray& data) const {
    return QMessageAuthenticationCode::hash(data, key, QCryptographicHash::Sha256);
}

QByteArray NativeSignalCryptoProvider::deriveMessageKey(const QByteArray& localPrivateKey, const QByteArray& remotePublicKey, const QByteArray& salt) const {
    QByteArray left = localPrivateKey;
    QByteArray right = remotePublicKey;
    if (right < left) {
        std::swap(left, right);
    }
    return hmac(salt, left + right + QByteArray(CryptoText::Protocol.toUtf8()));
}

QByteArray NativeSignalCryptoProvider::cryptWithKeystream(const QByteArray& input, const QByteArray& key, const QByteArray& iv) const {
    QByteArray output;
    output.resize(input.size());
    QByteArray stream;
    int block = 0;
    while (stream.size() < input.size()) {
        stream += digest(key + iv + intToBigEndian(block));
        ++block;
    }
    for (qsizetype index = 0; index < input.size(); ++index) {
        output[index] = static_cast<char>(input.at(index) ^ stream.at(index));
    }
    return output;
}

QByteArray NativeSignalCryptoProvider::aadFor(int counter, int previousCounter, const QByteArray& ratchetPublicKey) const {
    return intToBigEndian(counter) + intToBigEndian(previousCounter) + ratchetPublicKey;
}

QString NativeSignalCryptoProvider::sessionKey(const QString& userId, int deviceId) const {
    return QString("%1:%2").arg(userId).arg(deviceId);
}

int NativeSignalCryptoProvider::nextCounter(const QString& userId, int deviceId) {
    const QString key = sessionKey(userId, deviceId);
    const int counter = m_sendCounters.value(key, 0);
    m_sendCounters.insert(key, counter + 1);
    return counter;
}
