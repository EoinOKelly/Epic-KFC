#include "crypto/NativeSignalCryptoProvider.h"

#include "support/ClientConstants.h"

#include <QCryptographicHash>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMessageAuthenticationCode>
#include <QRandomGenerator>

#include <optional>

#if CLIENT_HAS_OPENSSL
#include <openssl/evp.h>
#include <openssl/hmac.h>
#include <openssl/kdf.h>
#include <openssl/rand.h>
#endif

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

#if CLIENT_HAS_OPENSSL
struct AeadResult {
    QByteArray ciphertext;
    QByteArray authTag;
};

struct RawKeyPair {
    QByteArray publicKey;
    QByteArray privateKey;
};

RawKeyPair generateRawKeyPair(int keyType) {
    EVP_PKEY_CTX* context = EVP_PKEY_CTX_new_id(keyType, nullptr);
    if (context == nullptr || EVP_PKEY_keygen_init(context) <= 0) {
        EVP_PKEY_CTX_free(context);
        return {};
    }

    EVP_PKEY* key = nullptr;
    if (EVP_PKEY_keygen(context, &key) <= 0) {
        EVP_PKEY_CTX_free(context);
        return {};
    }

    size_t publicLength = CryptoText::KeyBytes;
    size_t privateLength = CryptoText::KeyBytes;
    QByteArray publicKey(CryptoText::KeyBytes, Qt::Uninitialized);
    QByteArray privateKey(CryptoText::KeyBytes, Qt::Uninitialized);
    EVP_PKEY_get_raw_public_key(key, reinterpret_cast<unsigned char*>(publicKey.data()), &publicLength);
    EVP_PKEY_get_raw_private_key(key, reinterpret_cast<unsigned char*>(privateKey.data()), &privateLength);
    publicKey.resize(static_cast<qsizetype>(publicLength));
    privateKey.resize(static_cast<qsizetype>(privateLength));

    EVP_PKEY_free(key);
    EVP_PKEY_CTX_free(context);
    return {publicKey, privateKey};
}

QByteArray ed25519Sign(const QByteArray& privateKey, const QByteArray& message) {
    EVP_PKEY* key = EVP_PKEY_new_raw_private_key(EVP_PKEY_ED25519, nullptr, reinterpret_cast<const unsigned char*>(privateKey.constData()), privateKey.size());
    EVP_MD_CTX* context = EVP_MD_CTX_new();
    size_t signatureLength = 64;
    QByteArray signature(static_cast<qsizetype>(signatureLength), Qt::Uninitialized);
    if (key == nullptr || context == nullptr || EVP_DigestSignInit(context, nullptr, nullptr, nullptr, key) <= 0
        || EVP_DigestSign(context, reinterpret_cast<unsigned char*>(signature.data()), &signatureLength, reinterpret_cast<const unsigned char*>(message.constData()), message.size()) <= 0) {
        signature.clear();
    }
    signature.resize(static_cast<qsizetype>(signatureLength));
    EVP_MD_CTX_free(context);
    EVP_PKEY_free(key);
    return signature;
}

bool ed25519Verify(const QByteArray& publicKey, const QByteArray& message, const QByteArray& signature) {
    EVP_PKEY* key = EVP_PKEY_new_raw_public_key(EVP_PKEY_ED25519, nullptr, reinterpret_cast<const unsigned char*>(publicKey.constData()), publicKey.size());
    EVP_MD_CTX* context = EVP_MD_CTX_new();
    const int ok = key != nullptr && context != nullptr
        && EVP_DigestVerifyInit(context, nullptr, nullptr, nullptr, key) > 0
        && EVP_DigestVerify(context, reinterpret_cast<const unsigned char*>(signature.constData()), signature.size(), reinterpret_cast<const unsigned char*>(message.constData()), message.size()) == 1;
    EVP_MD_CTX_free(context);
    EVP_PKEY_free(key);
    return ok;
}

QByteArray x25519Dh(const QByteArray& privateKey, const QByteArray& publicKey) {
    EVP_PKEY* local = EVP_PKEY_new_raw_private_key(EVP_PKEY_X25519, nullptr, reinterpret_cast<const unsigned char*>(privateKey.constData()), privateKey.size());
    EVP_PKEY* remote = EVP_PKEY_new_raw_public_key(EVP_PKEY_X25519, nullptr, reinterpret_cast<const unsigned char*>(publicKey.constData()), publicKey.size());
    EVP_PKEY_CTX* context = EVP_PKEY_CTX_new(local, nullptr);
    size_t secretLength = CryptoText::KeyBytes;
    QByteArray secret(CryptoText::KeyBytes, Qt::Uninitialized);
    if (local == nullptr || remote == nullptr || context == nullptr
        || EVP_PKEY_derive_init(context) <= 0
        || EVP_PKEY_derive_set_peer(context, remote) <= 0
        || EVP_PKEY_derive(context, reinterpret_cast<unsigned char*>(secret.data()), &secretLength) <= 0) {
        secret.clear();
    }
    secret.resize(static_cast<qsizetype>(secretLength));
    EVP_PKEY_CTX_free(context);
    EVP_PKEY_free(remote);
    EVP_PKEY_free(local);
    return secret;
}

QByteArray hkdfSha256(const QByteArray& ikm, const QByteArray& salt, const QByteArray& info, int length) {
    QByteArray output(length, Qt::Uninitialized);
    EVP_PKEY_CTX* context = EVP_PKEY_CTX_new_id(EVP_PKEY_HKDF, nullptr);
    if (context == nullptr
        || EVP_PKEY_derive_init(context) <= 0
        || EVP_PKEY_CTX_set_hkdf_md(context, EVP_sha256()) <= 0
        || EVP_PKEY_CTX_set1_hkdf_salt(context, reinterpret_cast<const unsigned char*>(salt.constData()), salt.size()) <= 0
        || EVP_PKEY_CTX_set1_hkdf_key(context, reinterpret_cast<const unsigned char*>(ikm.constData()), ikm.size()) <= 0
        || EVP_PKEY_CTX_add1_hkdf_info(context, reinterpret_cast<const unsigned char*>(info.constData()), info.size()) <= 0) {
        output.clear();
        EVP_PKEY_CTX_free(context);
        return output;
    }

    size_t outputLength = static_cast<size_t>(output.size());
    if (EVP_PKEY_derive(context, reinterpret_cast<unsigned char*>(output.data()), &outputLength) <= 0) {
        output.clear();
    }
    output.resize(static_cast<qsizetype>(outputLength));
    EVP_PKEY_CTX_free(context);
    return output;
}

std::optional<AeadResult> aesGcmEncrypt(const QByteArray& plaintext, const QByteArray& key, const QByteArray& iv, const QByteArray& aad) {
    EVP_CIPHER_CTX* context = EVP_CIPHER_CTX_new();
    QByteArray ciphertext(plaintext.size(), Qt::Uninitialized);
    QByteArray tag(CryptoText::AuthTagBytes, Qt::Uninitialized);
    int outputLength = 0;
    int finalLength = 0;
    const bool ok = context != nullptr
        && EVP_EncryptInit_ex(context, EVP_aes_256_gcm(), nullptr, nullptr, nullptr) == 1
        && EVP_CIPHER_CTX_ctrl(context, EVP_CTRL_GCM_SET_IVLEN, iv.size(), nullptr) == 1
        && EVP_EncryptInit_ex(context, nullptr, nullptr, reinterpret_cast<const unsigned char*>(key.constData()), reinterpret_cast<const unsigned char*>(iv.constData())) == 1
        && (aad.isEmpty() || EVP_EncryptUpdate(context, nullptr, &outputLength, reinterpret_cast<const unsigned char*>(aad.constData()), aad.size()) == 1)
        && EVP_EncryptUpdate(context, reinterpret_cast<unsigned char*>(ciphertext.data()), &outputLength, reinterpret_cast<const unsigned char*>(plaintext.constData()), plaintext.size()) == 1
        && EVP_EncryptFinal_ex(context, reinterpret_cast<unsigned char*>(ciphertext.data()) + outputLength, &finalLength) == 1
        && EVP_CIPHER_CTX_ctrl(context, EVP_CTRL_GCM_GET_TAG, tag.size(), tag.data()) == 1;
    EVP_CIPHER_CTX_free(context);
    if (!ok) {
        return std::nullopt;
    }
    ciphertext.resize(outputLength + finalLength);
    return AeadResult{ciphertext, tag};
}

std::optional<QByteArray> aesGcmDecrypt(const QByteArray& ciphertext, const QByteArray& key, const QByteArray& iv, const QByteArray& aad, const QByteArray& tag) {
    EVP_CIPHER_CTX* context = EVP_CIPHER_CTX_new();
    QByteArray plaintext(ciphertext.size(), Qt::Uninitialized);
    int outputLength = 0;
    int finalLength = 0;
    const bool initialized = context != nullptr
        && EVP_DecryptInit_ex(context, EVP_aes_256_gcm(), nullptr, nullptr, nullptr) == 1
        && EVP_CIPHER_CTX_ctrl(context, EVP_CTRL_GCM_SET_IVLEN, iv.size(), nullptr) == 1
        && EVP_DecryptInit_ex(context, nullptr, nullptr, reinterpret_cast<const unsigned char*>(key.constData()), reinterpret_cast<const unsigned char*>(iv.constData())) == 1
        && (aad.isEmpty() || EVP_DecryptUpdate(context, nullptr, &outputLength, reinterpret_cast<const unsigned char*>(aad.constData()), aad.size()) == 1)
        && EVP_DecryptUpdate(context, reinterpret_cast<unsigned char*>(plaintext.data()), &outputLength, reinterpret_cast<const unsigned char*>(ciphertext.constData()), ciphertext.size()) == 1
        && EVP_CIPHER_CTX_ctrl(context, EVP_CTRL_GCM_SET_TAG, tag.size(), const_cast<char*>(tag.constData())) == 1;
    const bool finalized = initialized && EVP_DecryptFinal_ex(context, reinterpret_cast<unsigned char*>(plaintext.data()) + outputLength, &finalLength) == 1;
    EVP_CIPHER_CTX_free(context);
    if (!finalized) {
        return std::nullopt;
    }
    plaintext.resize(outputLength + finalLength);
    return plaintext;
}
#endif
}

bool NativeSignalCryptoProvider::isAvailable() const {
#if CLIENT_HAS_OPENSSL
    return true;
#else
    return false;
#endif
}

Result<DeviceKeyMaterial> NativeSignalCryptoProvider::loadOrCreateDevice(DeviceKeyMaterial existing, int deviceId) {
#if !CLIENT_HAS_OPENSSL
    Q_UNUSED(existing)
    Q_UNUSED(deviceId)
    return Result<DeviceKeyMaterial>::failure({ErrorCode::CryptoError, AppText::NativeCryptoUnavailable});
#else
    if (!existing.identityKey.isEmpty()) {
        return Result<DeviceKeyMaterial>::success(existing);
    }

    const RawKeyPair identity = generateRawKeyPair(EVP_PKEY_X25519);
    const RawKeyPair signing = generateRawKeyPair(EVP_PKEY_ED25519);
    const RawKeyPair signedPreKey = generateRawKeyPair(EVP_PKEY_X25519);
    const QByteArray signature = ed25519Sign(signing.privateKey, signedPreKey.publicKey);
    const bool keyGenerationFailed = identity.publicKey.size() != CryptoText::KeyBytes
        || identity.privateKey.size() != CryptoText::KeyBytes
        || signing.publicKey.size() != CryptoText::KeyBytes
        || signing.privateKey.size() != CryptoText::KeyBytes
        || signedPreKey.publicKey.size() != CryptoText::KeyBytes
        || signedPreKey.privateKey.size() != CryptoText::KeyBytes
        || signature.isEmpty();
    if (keyGenerationFailed) {
        return Result<DeviceKeyMaterial>::failure({ErrorCode::CryptoError, "OpenSSL key generation failed."});
    }

    const QByteArray identityPublic = identity.publicKey;
    const QByteArray identityPrivate = identity.privateKey;
    const QByteArray signingPublic = signing.publicKey;
    const QByteArray signingPrivate = signing.privateKey;
    const QByteArray signedPreKeyPublic = signedPreKey.publicKey;
    const QByteArray signedPreKeyPrivate = signedPreKey.privateKey;
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
#endif
}

Result<std::vector<OneTimePreKey>> NativeSignalCryptoProvider::createOneTimePreKeys(int deviceId, int count) {
#if !CLIENT_HAS_OPENSSL
    Q_UNUSED(deviceId)
    Q_UNUSED(count)
    return Result<std::vector<OneTimePreKey>>::failure({ErrorCode::CryptoError, AppText::NativeCryptoUnavailable});
#else
    std::vector<OneTimePreKey> preKeys;
    for (int index = 0; index < count; ++index) {
        const RawKeyPair keyPair = generateRawKeyPair(EVP_PKEY_X25519);
        if (keyPair.publicKey.size() != CryptoText::KeyBytes || keyPair.privateKey.size() != CryptoText::KeyBytes) {
            return Result<std::vector<OneTimePreKey>>::failure({ErrorCode::CryptoError, "OpenSSL one-time pre-key generation failed."});
        }
        const QByteArray publicKey = keyPair.publicKey;
        const QByteArray privateKey = keyPair.privateKey;
        preKeys.push_back({
            deviceId,
            CryptoText::FirstPreKeyId + index,
            toBase64(publicKey),
            toBase64(privateKey),
            false
        });
    }
    return Result<std::vector<OneTimePreKey>>::success(preKeys);
#endif
}

Result<bool> NativeSignalCryptoProvider::verifySignedPreKey(const PreKeyBundle& bundle) {
#if !CLIENT_HAS_OPENSSL
    Q_UNUSED(bundle)
    return Result<bool>::failure({ErrorCode::CryptoError, AppText::NativeCryptoUnavailable});
#else
    const bool hasRequiredFields = isValidBase64(bundle.identityKey)
        && isValidBase64(bundle.identitySigningKey)
        && isValidBase64(bundle.signedPreKey)
        && isValidBase64(bundle.signedPreKeySignature);
    if (!hasRequiredFields) {
        return Result<bool>::failure({ErrorCode::CryptoError, "Pre-key bundle contains invalid base64 fields."});
    }
    const bool signatureValid = ed25519Verify(fromBase64(bundle.identitySigningKey), fromBase64(bundle.signedPreKey), fromBase64(bundle.signedPreKeySignature));
    if (!signatureValid) {
        return Result<bool>::failure({ErrorCode::CryptoError, "Pre-key bundle signature is invalid."});
    }
    return Result<bool>::success(true);
#endif
}

Result<EncryptedPayload> NativeSignalCryptoProvider::encrypt(
    const QString& senderUserId,
    const DeviceKeyMaterial& senderDevice,
    const PreKeyBundle& recipientBundle,
    const QString& plaintext) {
    Q_UNUSED(senderUserId)
#if !CLIENT_HAS_OPENSSL
    Q_UNUSED(senderDevice)
    Q_UNUSED(recipientBundle)
    Q_UNUSED(plaintext)
    return Result<EncryptedPayload>::failure({ErrorCode::CryptoError, AppText::NativeCryptoUnavailable});
#else
    if (plaintext.trimmed().isEmpty()) {
        return Result<EncryptedPayload>::failure({ErrorCode::CryptoError, AppText::EmptyMessage});
    }

    const int counter = nextCounter(recipientBundle.userId, recipientBundle.deviceId);
    const int previousCounter = 0;
    const RawKeyPair ratchetKey = generateRawKeyPair(EVP_PKEY_X25519);
    const RawKeyPair ephemeralKey = generateRawKeyPair(EVP_PKEY_X25519);
    if (ratchetKey.publicKey.size() != CryptoText::KeyBytes || ephemeralKey.publicKey.size() != CryptoText::KeyBytes) {
        return Result<EncryptedPayload>::failure({ErrorCode::CryptoError, "OpenSSL ratchet key generation failed."});
    }

    const QByteArray dh1 = x25519Dh(fromBase64(senderDevice.identityPrivateKey), fromBase64(recipientBundle.signedPreKey));
    const QByteArray dh2 = x25519Dh(ephemeralKey.privateKey, fromBase64(recipientBundle.identityKey));
    const QByteArray dh3 = x25519Dh(ephemeralKey.privateKey, fromBase64(recipientBundle.signedPreKey));
    QByteArray dhOutputs = dh1 + dh2 + dh3;
    if (!recipientBundle.oneTimePreKey.isEmpty()) {
        dhOutputs += x25519Dh(ephemeralKey.privateKey, fromBase64(recipientBundle.oneTimePreKey));
    }
    const QByteArray sharedSecret = kdfX3dh(dhOutputs);
    const QByteArray key = firstRatchetMessageKey(sharedSecret, ratchetKey.privateKey, fromBase64(recipientBundle.signedPreKey));
    const QByteArray ratchetPublicKey = ratchetKey.publicKey;
    if (key.size() != CryptoText::KeyBytes) {
        return Result<EncryptedPayload>::failure({ErrorCode::CryptoError, "Could not derive message key."});
    }

    const QByteArray iv = randomBytes(CryptoText::IvBytes);
    const QByteArray aad = aadFor(counter, previousCounter, ratchetPublicKey);
    const auto encrypted = aesGcmEncrypt(plaintext.toUtf8(), key, iv, aad);
    if (!encrypted.has_value()) {
        return Result<EncryptedPayload>::failure({ErrorCode::CryptoError, "AES-256-GCM encryption failed."});
    }
    const QByteArray ciphertext = encrypted->ciphertext;
    const QByteArray tag = encrypted->authTag;

    QJsonObject root{
        {CryptoText::WireCounter, counter},
        {CryptoText::WirePreviousCounter, previousCounter},
        {CryptoText::WireCiphertext, toBase64(ciphertext)},
        {CryptoText::WireIv, toBase64(iv)},
        {CryptoText::WireAuthTag, toBase64(tag)},
        {CryptoText::WireRatchetPublicKey, toBase64(ratchetPublicKey)}
    };

    if (counter == 0) {
        const QByteArray ephemeral = ephemeralKey.publicKey;
        root.insert(CryptoText::WireX3dh, QJsonObject{
            {CryptoText::WireIdentityKey, senderDevice.identityKey},
            {CryptoText::WireEphemeralKey, toBase64(ephemeral)}
        });
    }

    return Result<EncryptedPayload>::success({
        QString::fromUtf8(QJsonDocument(root).toJson(QJsonDocument::Compact)),
        recipientBundle.oneTimePreKeyId
    });
#endif
}

Result<QString> NativeSignalCryptoProvider::decrypt(
    const QString& currentUserId,
    const DeviceKeyMaterial& currentDevice,
    const LocalMessage& message,
    const std::optional<OneTimePreKey>& oneTimePreKey) {
    Q_UNUSED(currentUserId)
#if !CLIENT_HAS_OPENSSL
    Q_UNUSED(currentDevice)
    Q_UNUSED(message)
    Q_UNUSED(oneTimePreKey)
    return Result<QString>::failure({ErrorCode::CryptoError, AppText::NativeCryptoUnavailable});
#else
    const QJsonObject root = QJsonDocument::fromJson(message.wirePayloadJson.toUtf8()).object();
    const int counter = root.value(CryptoText::WireCounter).toInt();
    const int previousCounter = root.value(CryptoText::WirePreviousCounter).toInt();
    const QByteArray ratchetPublicKey = fromBase64(root.value(CryptoText::WireRatchetPublicKey).toString());
    const QJsonObject x3dh = root.value(CryptoText::WireX3dh).toObject();
    if (x3dh.isEmpty()) {
        return Result<QString>::failure({ErrorCode::CryptoError, "Ratchet session state is not available for this message yet."});
    }

    const QByteArray remoteIdentityKey = fromBase64(x3dh.value(CryptoText::WireIdentityKey).toString());
    const QByteArray remoteEphemeralKey = fromBase64(x3dh.value(CryptoText::WireEphemeralKey).toString());
    const QByteArray dh1 = x25519Dh(fromBase64(currentDevice.signedPreKeyPrivate), remoteIdentityKey);
    const QByteArray dh2 = x25519Dh(fromBase64(currentDevice.identityPrivateKey), remoteEphemeralKey);
    const QByteArray dh3 = x25519Dh(fromBase64(currentDevice.signedPreKeyPrivate), remoteEphemeralKey);
    QByteArray dhOutputs = dh1 + dh2 + dh3;
    if (message.consumedOneTimePreKeyId.has_value()) {
        if (!oneTimePreKey.has_value()) {
            return Result<QString>::failure({ErrorCode::CryptoError, "Required one-time pre-key private material is unavailable."});
        }
        dhOutputs += x25519Dh(fromBase64(oneTimePreKey->privateKey), remoteEphemeralKey);
    }

    const QByteArray sharedSecret = kdfX3dh(dhOutputs);
    const QByteArray key = firstRatchetMessageKey(sharedSecret, fromBase64(currentDevice.signedPreKeyPrivate), ratchetPublicKey);
    if (key.size() != CryptoText::KeyBytes) {
        return Result<QString>::failure({ErrorCode::CryptoError, "Could not derive message key."});
    }
    const QByteArray iv = fromBase64(root.value(CryptoText::WireIv).toString());
    const QByteArray ciphertext = fromBase64(root.value(CryptoText::WireCiphertext).toString());
    const QByteArray receivedTag = fromBase64(root.value(CryptoText::WireAuthTag).toString());
    const QByteArray aad = aadFor(counter, previousCounter, ratchetPublicKey);
    const auto plaintext = aesGcmDecrypt(ciphertext, key, iv, aad, receivedTag);
    if (!plaintext.has_value()) {
        return Result<QString>::failure({ErrorCode::CryptoError, "Message authentication failed."});
    }
    return Result<QString>::success(QString::fromUtf8(*plaintext));
#endif
}

QByteArray NativeSignalCryptoProvider::randomBytes(qsizetype size) const {
    QByteArray bytes(size, Qt::Uninitialized);
#if CLIENT_HAS_OPENSSL
    if (RAND_bytes(reinterpret_cast<unsigned char*>(bytes.data()), static_cast<int>(bytes.size())) == 1) {
        return bytes;
    }
#endif
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
#if CLIENT_HAS_OPENSSL
    unsigned int length = 0;
    QByteArray output(EVP_MAX_MD_SIZE, Qt::Uninitialized);
    HMAC(EVP_sha256(),
        key.constData(),
        key.size(),
        reinterpret_cast<const unsigned char*>(data.constData()),
        data.size(),
        reinterpret_cast<unsigned char*>(output.data()),
        &length);
    output.resize(static_cast<qsizetype>(length));
    return output;
#else
    return QMessageAuthenticationCode::hash(data, key, QCryptographicHash::Sha256);
#endif
}

QByteArray NativeSignalCryptoProvider::deriveMessageKey(const QByteArray& localPrivateKey, const QByteArray& remotePublicKey, const QByteArray& salt) const {
    QByteArray left = localPrivateKey;
    QByteArray right = remotePublicKey;
    if (right < left) {
        std::swap(left, right);
    }
    return hmac(salt, left + right + QByteArray(CryptoText::Protocol.toUtf8()));
}

QByteArray NativeSignalCryptoProvider::kdfX3dh(const QByteArray& dhOutputs) const {
#if CLIENT_HAS_OPENSSL
    return hkdfSha256(dhOutputs, QByteArray(CryptoText::KeyBytes, 0), CryptoText::X3dhInfo.toUtf8(), CryptoText::KeyBytes);
#else
    Q_UNUSED(dhOutputs)
    return {};
#endif
}

QByteArray NativeSignalCryptoProvider::firstRatchetMessageKey(const QByteArray& rootKey, const QByteArray& localRatchetPrivateKey, const QByteArray& remoteRatchetPublicKey) const {
#if CLIENT_HAS_OPENSSL
    const QByteArray dhOutput = x25519Dh(localRatchetPrivateKey, remoteRatchetPublicKey);
    const QByteArray rootOut = hkdfSha256(dhOutput, rootKey, {}, CryptoText::KeyBytes * 2);
    const QByteArray chainKey = rootOut.mid(CryptoText::KeyBytes, CryptoText::KeyBytes);
    return hmac(chainKey, QByteArray(1, char(0x01))).left(CryptoText::KeyBytes);
#else
    Q_UNUSED(rootKey)
    Q_UNUSED(localRatchetPrivateKey)
    Q_UNUSED(remoteRatchetPublicKey)
    return {};
#endif
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
    const auto foundCounter = m_sendCounters.find(key);
    const int counter = foundCounter == m_sendCounters.end() ? 0 : foundCounter->second;
    m_sendCounters.insert_or_assign(key, counter + 1);
    return counter;
}
