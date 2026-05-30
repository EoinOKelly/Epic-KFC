#include "storage/JsonLocalStore.h"

#include "support/ClientConstants.h"

#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>

#include <algorithm>
#include <map>
#include <optional>
#include <utility>
#include <vector>

#if CLIENT_HAS_OPENSSL
#include <openssl/evp.h>
#include <openssl/rand.h>
#endif

namespace {
constexpr int SecretBlobVersion = 1;
constexpr int SecretPbkdf2Iterations = 210000;
constexpr qsizetype SecretSaltBytes = 16;
constexpr qsizetype SecretIvBytes = 12;
constexpr qsizetype SecretTagBytes = 16;
constexpr qsizetype SecretKeyBytes = 32;

const QString SecretSaltKey = "secretSalt";
const QString SecretVersionKey = "version";
const QString SecretKdfKey = "kdf";
const QString SecretIterationsKey = "iterations";
const QString SecretIvKey = "iv";
const QString SecretAuthTagKey = "authTag";
const QString SecretCiphertextKey = "ciphertext";
const QString SecretKdfName = "PBKDF2-HMAC-SHA256";

QJsonObject userToJson(const UserProfile& user) {
    return {
        {StorageKeys::Id, user.id},
        {StorageKeys::Username, user.username},
        {StorageKeys::Email, user.email}
    };
}

UserProfile userFromJson(const QJsonObject& object) {
    return {
        object.value(StorageKeys::Id).toString(),
        object.value(StorageKeys::Username).toString(),
        object.value(StorageKeys::Email).toString()
    };
}

QJsonObject sessionToJson(const AuthSession& session) {
    return {
        {StorageKeys::CurrentUser, userToJson(session.user)},
        {StorageKeys::AccessToken, session.tokens.accessToken},
        {StorageKeys::RefreshToken, session.tokens.refreshToken}
    };
}

AuthSession sessionFromJson(const QJsonObject& object) {
    return {
        userFromJson(object.value(StorageKeys::CurrentUser).toObject()),
        {
            object.value(StorageKeys::AccessToken).toString(),
            object.value(StorageKeys::RefreshToken).toString(),
            "bearer",
            0
        }
    };
}

QJsonObject deviceToJson(const DeviceKeyMaterial& material) {
    return {
        {StorageKeys::DeviceId, material.deviceId},
        {StorageKeys::RegistrationId, material.registrationId},
        {StorageKeys::IdentityKey, material.identityKey},
        {StorageKeys::IdentityPrivateKey, material.identityPrivateKey},
        {StorageKeys::IdentitySigningKey, material.identitySigningKey},
        {StorageKeys::IdentitySigningPrivateKey, material.identitySigningPrivateKey},
        {StorageKeys::SignedPreKeyId, material.signedPreKeyId},
        {StorageKeys::SignedPreKey, material.signedPreKey},
        {StorageKeys::SignedPreKeyPrivate, material.signedPreKeyPrivate},
        {StorageKeys::SignedPreKeySignature, material.signedPreKeySignature}
    };
}

DeviceKeyMaterial deviceFromJson(const QJsonObject& object) {
    return {
        object.value(StorageKeys::DeviceId).toInt(),
        object.value(StorageKeys::RegistrationId).toInt(),
        object.value(StorageKeys::IdentityKey).toString(),
        object.value(StorageKeys::IdentityPrivateKey).toString(),
        object.value(StorageKeys::IdentitySigningKey).toString(),
        object.value(StorageKeys::IdentitySigningPrivateKey).toString(),
        object.value(StorageKeys::SignedPreKeyId).toInt(),
        object.value(StorageKeys::SignedPreKey).toString(),
        object.value(StorageKeys::SignedPreKeyPrivate).toString(),
        object.value(StorageKeys::SignedPreKeySignature).toString()
    };
}

QJsonObject preKeyToJson(const OneTimePreKey& preKey) {
    return {
        {StorageKeys::DeviceId, preKey.deviceId},
        {StorageKeys::PreKeyId, preKey.preKeyId},
        {StorageKeys::PreKeyPublic, preKey.publicKey},
        {StorageKeys::PreKeyPrivate, preKey.privateKey},
        {"uploaded", preKey.uploaded}
    };
}

OneTimePreKey preKeyFromJson(const QJsonObject& object) {
    return {
        object.value(StorageKeys::DeviceId).toInt(),
        object.value(StorageKeys::PreKeyId).toInt(),
        object.value(StorageKeys::PreKeyPublic).toString(),
        object.value(StorageKeys::PreKeyPrivate).toString(),
        object.value("uploaded").toBool()
    };
}

QJsonObject trustPinToJson(const TrustPin& pin) {
    return {
        {StorageKeys::UserId, pin.userId},
        {StorageKeys::DeviceId, pin.deviceId},
        {StorageKeys::IdentityKey, pin.identityKey},
        {StorageKeys::FirstSeenAt, pin.firstSeenAt.toUTC().toString(Qt::ISODateWithMs)}
    };
}

TrustPin trustPinFromJson(const QJsonObject& object) {
    return {
        object.value(StorageKeys::UserId).toString(),
        object.value(StorageKeys::DeviceId).toInt(),
        object.value(StorageKeys::IdentityKey).toString(),
        QDateTime::fromString(object.value(StorageKeys::FirstSeenAt).toString(), Qt::ISODateWithMs)
    };
}

QJsonObject messageToJson(const LocalMessage& message) {
    return {
        {StorageKeys::Id, message.id},
        {StorageKeys::SenderUserId, message.senderUserId},
        {StorageKeys::SenderDeviceId, message.senderDeviceId},
        {StorageKeys::RecipientUserId, message.recipientUserId},
        {StorageKeys::RecipientDeviceId, message.recipientDeviceId},
        {StorageKeys::WirePayloadJson, message.wirePayloadJson},
        {StorageKeys::ConsumedOneTimePreKeyId, message.consumedOneTimePreKeyId.has_value() ? QJsonValue(*message.consumedOneTimePreKeyId) : QJsonValue::Null},
        {StorageKeys::CreatedAt, message.createdAt.toUTC().toString(Qt::ISODateWithMs)},
        {StorageKeys::AccessRevokedAt, message.accessRevokedAt},
        {StorageKeys::SenderDeletedAt, message.senderDeletedAt},
        {StorageKeys::RecipientDeletedAt, message.recipientDeletedAt},
        {StorageKeys::DeletedAt, message.deletedAt},
        {"direction", message.direction == MessageDirection::Sent ? "sent" : "received"}
    };
}

LocalMessage messageFromJson(const QJsonObject& object) {
    return {
        object.value(StorageKeys::Id).toString(),
        object.value(StorageKeys::SenderUserId).toString(),
        object.value(StorageKeys::SenderDeviceId).toInt(),
        object.value(StorageKeys::RecipientUserId).toString(),
        object.value(StorageKeys::RecipientDeviceId).toInt(),
        object.value(StorageKeys::WirePayloadJson).toString(),
        object.value(StorageKeys::ConsumedOneTimePreKeyId).isDouble()
            ? std::optional<int>(object.value(StorageKeys::ConsumedOneTimePreKeyId).toInt())
            : std::nullopt,
        QDateTime::fromString(object.value(StorageKeys::CreatedAt).toString(), Qt::ISODateWithMs),
        object.value(StorageKeys::AccessRevokedAt).toString(),
        object.value(StorageKeys::SenderDeletedAt).toString(),
        object.value(StorageKeys::RecipientDeletedAt).toString(),
        object.value(StorageKeys::DeletedAt).toString(),
        object.value("direction").toString() == "sent" ? MessageDirection::Sent : MessageDirection::Received
    };
}

QByteArray base64ToBytes(const QString& value) {
    return QByteArray::fromBase64(value.toLatin1());
}

QString bytesToBase64(const QByteArray& value) {
    return QString::fromLatin1(value.toBase64());
}

QByteArray randomBytes(qsizetype size) {
    QByteArray bytes(size, Qt::Uninitialized);
#if CLIENT_HAS_OPENSSL
    if (RAND_bytes(reinterpret_cast<unsigned char*>(bytes.data()), static_cast<int>(bytes.size())) == 1) {
        return bytes;
    }
#endif
    bytes.clear();
    return bytes;
}

#if CLIENT_HAS_OPENSSL
std::optional<QByteArray> deriveStorageKey(const QString& passphrase, const QByteArray& salt) {
    QByteArray key(SecretKeyBytes, Qt::Uninitialized);
    const QByteArray passphraseBytes = passphrase.toUtf8();
    const int ok = PKCS5_PBKDF2_HMAC(
        passphraseBytes.constData(),
        passphraseBytes.size(),
        reinterpret_cast<const unsigned char*>(salt.constData()),
        salt.size(),
        SecretPbkdf2Iterations,
        EVP_sha256(),
        key.size(),
        reinterpret_cast<unsigned char*>(key.data()));
    if (ok != 1) {
        return std::nullopt;
    }
    return key;
}

std::optional<QJsonObject> encryptSecretString(const QString& value, const QString& fieldName, const QString& passphrase, const QByteArray& salt) {
    const auto key = deriveStorageKey(passphrase, salt);
    if (!key.has_value()) {
        return std::nullopt;
    }

    const QByteArray iv = randomBytes(SecretIvBytes);
    if (iv.size() != SecretIvBytes) {
        return std::nullopt;
    }

    const QByteArray plaintext = value.toUtf8();
    const QByteArray aad = fieldName.toUtf8();
    QByteArray ciphertext(plaintext.size(), Qt::Uninitialized);
    QByteArray tag(SecretTagBytes, Qt::Uninitialized);
    EVP_CIPHER_CTX* context = EVP_CIPHER_CTX_new();
    int outputLength = 0;
    int finalLength = 0;
    const bool ok = context != nullptr
        && EVP_EncryptInit_ex(context, EVP_aes_256_gcm(), nullptr, nullptr, nullptr) == 1
        && EVP_CIPHER_CTX_ctrl(context, EVP_CTRL_GCM_SET_IVLEN, iv.size(), nullptr) == 1
        && EVP_EncryptInit_ex(context, nullptr, nullptr, reinterpret_cast<const unsigned char*>(key->constData()), reinterpret_cast<const unsigned char*>(iv.constData())) == 1
        && EVP_EncryptUpdate(context, nullptr, &outputLength, reinterpret_cast<const unsigned char*>(aad.constData()), aad.size()) == 1
        && EVP_EncryptUpdate(context, reinterpret_cast<unsigned char*>(ciphertext.data()), &outputLength, reinterpret_cast<const unsigned char*>(plaintext.constData()), plaintext.size()) == 1
        && EVP_EncryptFinal_ex(context, reinterpret_cast<unsigned char*>(ciphertext.data()) + outputLength, &finalLength) == 1
        && EVP_CIPHER_CTX_ctrl(context, EVP_CTRL_GCM_GET_TAG, tag.size(), tag.data()) == 1;
    EVP_CIPHER_CTX_free(context);
    if (!ok) {
        return std::nullopt;
    }

    ciphertext.resize(outputLength + finalLength);
    return QJsonObject{
        {SecretVersionKey, SecretBlobVersion},
        {SecretKdfKey, SecretKdfName},
        {SecretIterationsKey, SecretPbkdf2Iterations},
        {SecretIvKey, bytesToBase64(iv)},
        {SecretAuthTagKey, bytesToBase64(tag)},
        {SecretCiphertextKey, bytesToBase64(ciphertext)}
    };
}

std::optional<QString> decryptSecretString(const QJsonObject& blob, const QString& fieldName, const QString& passphrase, const QByteArray& salt) {
    if (blob.value(SecretVersionKey).toInt() != SecretBlobVersion) {
        return std::nullopt;
    }

    const auto key = deriveStorageKey(passphrase, salt);
    if (!key.has_value()) {
        return std::nullopt;
    }

    const QByteArray iv = base64ToBytes(blob.value(SecretIvKey).toString());
    const QByteArray tag = base64ToBytes(blob.value(SecretAuthTagKey).toString());
    const QByteArray ciphertext = base64ToBytes(blob.value(SecretCiphertextKey).toString());
    const QByteArray aad = fieldName.toUtf8();
    QByteArray plaintext(ciphertext.size(), Qt::Uninitialized);
    EVP_CIPHER_CTX* context = EVP_CIPHER_CTX_new();
    int outputLength = 0;
    int finalLength = 0;
    const bool initialized = context != nullptr
        && EVP_DecryptInit_ex(context, EVP_aes_256_gcm(), nullptr, nullptr, nullptr) == 1
        && EVP_CIPHER_CTX_ctrl(context, EVP_CTRL_GCM_SET_IVLEN, iv.size(), nullptr) == 1
        && EVP_DecryptInit_ex(context, nullptr, nullptr, reinterpret_cast<const unsigned char*>(key->constData()), reinterpret_cast<const unsigned char*>(iv.constData())) == 1
        && EVP_DecryptUpdate(context, nullptr, &outputLength, reinterpret_cast<const unsigned char*>(aad.constData()), aad.size()) == 1
        && EVP_DecryptUpdate(context, reinterpret_cast<unsigned char*>(plaintext.data()), &outputLength, reinterpret_cast<const unsigned char*>(ciphertext.constData()), ciphertext.size()) == 1
        && EVP_CIPHER_CTX_ctrl(context, EVP_CTRL_GCM_SET_TAG, tag.size(), const_cast<char*>(tag.constData())) == 1;
    const bool finalized = initialized && EVP_DecryptFinal_ex(context, reinterpret_cast<unsigned char*>(plaintext.data()) + outputLength, &finalLength) == 1;
    EVP_CIPHER_CTX_free(context);
    if (!finalized) {
        return std::nullopt;
    }

    plaintext.resize(outputLength + finalLength);
    return QString::fromUtf8(plaintext);
}
#endif

Result<bool> protectString(QJsonObject& object, const QString& key, const QString& passphrase, const QByteArray& salt) {
#if !CLIENT_HAS_OPENSSL
    Q_UNUSED(object)
    Q_UNUSED(key)
    Q_UNUSED(passphrase)
    Q_UNUSED(salt)
    return Result<bool>::failure({ErrorCode::StorageError, AppText::NativeCryptoUnavailable});
#else
    const QJsonValue value = object.value(key);
    if (value.isUndefined() || value.isNull() || value.isObject()) {
        return Result<bool>::success(true);
    }

    const auto encrypted = encryptSecretString(value.toString(), key, passphrase, salt);
    if (!encrypted.has_value()) {
        return Result<bool>::failure({ErrorCode::StorageError, QString("Could not encrypt local secret field %1.").arg(key)});
    }
    object.insert(key, *encrypted);
    return Result<bool>::success(true);
#endif
}

Result<bool> unprotectString(QJsonObject& object, const QString& key, const QString& passphrase, const QByteArray& salt) {
#if !CLIENT_HAS_OPENSSL
    Q_UNUSED(object)
    Q_UNUSED(key)
    Q_UNUSED(passphrase)
    Q_UNUSED(salt)
    return Result<bool>::failure({ErrorCode::StorageError, AppText::NativeCryptoUnavailable});
#else
    const QJsonValue value = object.value(key);
    if (value.isUndefined() || value.isNull() || !value.isObject()) {
        return Result<bool>::success(true);
    }

    const auto plaintext = decryptSecretString(value.toObject(), key, passphrase, salt);
    if (!plaintext.has_value()) {
        return Result<bool>::failure({ErrorCode::StorageError, QString("Could not decrypt local secret field %1.").arg(key)});
    }
    object.insert(key, *plaintext);
    return Result<bool>::success(true);
#endif
}

Result<bool> protectStrings(QJsonObject& object, const std::vector<QString>& keys, const QString& passphrase, const QByteArray& salt) {
    for (const auto& key : keys) {
        const auto result = protectString(object, key, passphrase, salt);
        if (result.failed()) {
            return result;
        }
    }
    return Result<bool>::success(true);
}

Result<bool> unprotectStrings(QJsonObject& object, const std::vector<QString>& keys, const QString& passphrase, const QByteArray& salt) {
    for (const auto& key : keys) {
        const auto result = unprotectString(object, key, passphrase, salt);
        if (result.failed()) {
            return result;
        }
    }
    return Result<bool>::success(true);
}
}

JsonLocalStore::JsonLocalStore(QString path, bool secretProtectionRequired)
    : m_path(std::move(path))
    , m_secretProtectionRequired(secretProtectionRequired) {
    load();
}

void JsonLocalStore::setSecretProtectionRequired(bool required) {
    m_secretProtectionRequired = required;
}

void JsonLocalStore::setSecretPassphrase(QString passphrase) {
    m_secretPassphrase = std::move(passphrase);
}

void JsonLocalStore::clearSecretPassphrase() {
    m_secretPassphrase.clear();
}

Result<bool> JsonLocalStore::reload() {
    return load();
}

Result<bool> JsonLocalStore::saveSession(const AuthSession& session) {
    m_session = session;
    m_hasSession = true;
    return save();
}

Result<std::optional<AuthSession>> JsonLocalStore::loadSession() const {
    if (!m_hasSession) {
        return Result<std::optional<AuthSession>>::success(std::nullopt);
    }
    return Result<std::optional<AuthSession>>::success(m_session);
}

Result<bool> JsonLocalStore::clearSession() {
    m_hasSession = false;
    m_session = {};
    return save();
}

Result<bool> JsonLocalStore::saveDeviceKeys(const DeviceKeyMaterial& material) {
    auto it = std::find_if(m_deviceKeys.begin(), m_deviceKeys.end(), [&material](const DeviceKeyMaterial& existing) {
        return existing.deviceId == material.deviceId;
    });
    if (it == m_deviceKeys.end()) {
        m_deviceKeys.push_back(material);
    } else {
        *it = material;
    }
    return save();
}

Result<std::optional<DeviceKeyMaterial>> JsonLocalStore::loadDeviceKeys(int deviceId) const {
    const auto it = std::find_if(m_deviceKeys.cbegin(), m_deviceKeys.cend(), [deviceId](const DeviceKeyMaterial& material) {
        return material.deviceId == deviceId;
    });
    if (it == m_deviceKeys.cend()) {
        return Result<std::optional<DeviceKeyMaterial>>::success(std::nullopt);
    }
    return Result<std::optional<DeviceKeyMaterial>>::success(*it);
}

Result<bool> JsonLocalStore::saveOneTimePreKeys(const std::vector<OneTimePreKey>& preKeys) {
    for (const auto& preKey : preKeys) {
        auto it = std::find_if(m_oneTimePreKeys.begin(), m_oneTimePreKeys.end(), [&preKey](const OneTimePreKey& existing) {
            return existing.deviceId == preKey.deviceId && existing.preKeyId == preKey.preKeyId;
        });
        if (it == m_oneTimePreKeys.end()) {
            m_oneTimePreKeys.push_back(preKey);
        } else {
            *it = preKey;
        }
    }
    return save();
}

Result<std::vector<OneTimePreKey>> JsonLocalStore::loadOneTimePreKeys(int deviceId) const {
    std::vector<OneTimePreKey> matching;
    std::copy_if(m_oneTimePreKeys.cbegin(), m_oneTimePreKeys.cend(), std::back_inserter(matching), [deviceId](const OneTimePreKey& preKey) {
        return preKey.deviceId == deviceId;
    });
    return Result<std::vector<OneTimePreKey>>::success(matching);
}

Result<bool> JsonLocalStore::saveTrustPin(const TrustPin& pin) {
    auto it = std::find_if(m_trustPins.begin(), m_trustPins.end(), [&pin](const TrustPin& existing) {
        return existing.userId == pin.userId && existing.deviceId == pin.deviceId;
    });
    if (it == m_trustPins.end()) {
        m_trustPins.push_back(pin);
    } else {
        *it = pin;
    }
    return save();
}

Result<std::optional<TrustPin>> JsonLocalStore::trustPin(const QString& userId, int deviceId) const {
    const auto it = std::find_if(m_trustPins.cbegin(), m_trustPins.cend(), [&userId, deviceId](const TrustPin& pin) {
        return pin.userId == userId && pin.deviceId == deviceId;
    });
    if (it == m_trustPins.cend()) {
        return Result<std::optional<TrustPin>>::success(std::nullopt);
    }
    return Result<std::optional<TrustPin>>::success(*it);
}

Result<bool> JsonLocalStore::saveMessage(const LocalMessage& message) {
    auto it = std::find_if(m_messages.begin(), m_messages.end(), [&message](const LocalMessage& existing) {
        return existing.id == message.id;
    });
    if (it == m_messages.end()) {
        m_messages.push_back(message);
    } else {
        *it = message;
    }
    return save();
}

Result<std::optional<LocalMessage>> JsonLocalStore::findMessage(const QString& messageId) const {
    const auto it = std::find_if(m_messages.cbegin(), m_messages.cend(), [&messageId](const LocalMessage& message) {
        return message.id == messageId;
    });
    if (it == m_messages.cend()) {
        return Result<std::optional<LocalMessage>>::success(std::nullopt);
    }
    return Result<std::optional<LocalMessage>>::success(*it);
}

Result<MessageList> JsonLocalStore::allMessages() const {
    return Result<MessageList>::success(m_messages);
}

Result<ConversationList> JsonLocalStore::conversationsFor(const QString& currentUserId) const {
    std::map<QString, ConversationSummary> summaries;
    for (const auto& message : m_messages) {
        const bool sentByCurrentUser = message.senderUserId == currentUserId;
        const QString peerUserId = sentByCurrentUser ? message.recipientUserId : message.senderUserId;
        const int peerDeviceId = sentByCurrentUser ? message.recipientDeviceId : message.senderDeviceId;
        const QString key = QString("%1:%2").arg(peerUserId).arg(peerDeviceId);
        auto summary = summaries.contains(key) ? summaries.at(key) : ConversationSummary{peerUserId, peerDeviceId, 0, {}};
        summary.messageCount += 1;
        if (!summary.latestMessageAt.isValid() || message.createdAt > summary.latestMessageAt) {
            summary.latestMessageAt = message.createdAt;
        }
        summaries.insert_or_assign(key, summary);
    }
    ConversationList conversations;
    std::transform(summaries.cbegin(), summaries.cend(), std::back_inserter(conversations), [](const auto& entry) {
        return entry.second;
    });
    return Result<ConversationList>::success(conversations);
}

Result<bool> JsonLocalStore::load() {
    m_session = {};
    m_hasSession = false;
    m_deviceKeys.clear();
    m_oneTimePreKeys.clear();
    m_trustPins.clear();
    m_messages.clear();

    QFile file(m_path);
    if (!file.exists()) {
        return Result<bool>::success(true);
    }
    if (!file.open(QIODevice::ReadOnly)) {
        return Result<bool>::failure({ErrorCode::StorageError, QString("Could not read %1.").arg(m_path)});
    }

    QJsonObject root = QJsonDocument::fromJson(file.readAll()).object();
    if (root.contains(SecretSaltKey)) {
        m_secretSalt = base64ToBytes(root.value(SecretSaltKey).toString());
        if (m_secretPassphrase.isEmpty()) {
            return Result<bool>::success(true);
        }

        const auto unprotectedRoot = unprotectSecrets(root);
        if (unprotectedRoot.failed()) {
            return Result<bool>::failure(unprotectedRoot.error());
        }
        root = unprotectedRoot.value();
    }

    if (root.contains("session")) {
        m_session = sessionFromJson(root.value("session").toObject());
        m_hasSession = !m_session.tokens.accessToken.isEmpty();
    }
    for (const auto value : root.value(StorageKeys::DeviceKeys).toArray()) {
        m_deviceKeys.push_back(deviceFromJson(value.toObject()));
    }
    for (const auto value : root.value(StorageKeys::OneTimePreKeys).toArray()) {
        m_oneTimePreKeys.push_back(preKeyFromJson(value.toObject()));
    }
    for (const auto value : root.value(StorageKeys::TrustPins).toArray()) {
        m_trustPins.push_back(trustPinFromJson(value.toObject()));
    }
    for (const auto value : root.value(StorageKeys::Messages).toArray()) {
        m_messages.push_back(messageFromJson(value.toObject()));
    }
    return Result<bool>::success(true);
}

Result<bool> JsonLocalStore::save() const {
    QDir directory = QFileInfo(m_path).absoluteDir();
    const bool directoryReady = directory.exists() || directory.mkpath(".");
    if (!directoryReady) {
        return Result<bool>::failure({ErrorCode::StorageError, QString("Could not create %1.").arg(directory.path())});
    }

    QJsonObject root;
    root.insert(StorageKeys::RootVersion, 1);
    if (m_hasSession) {
        root.insert("session", sessionToJson(m_session));
    }

    QJsonArray devices;
    for (const auto& device : m_deviceKeys) {
        devices.push_back(deviceToJson(device));
    }
    root.insert(StorageKeys::DeviceKeys, devices);

    QJsonArray preKeys;
    for (const auto& preKey : m_oneTimePreKeys) {
        preKeys.push_back(preKeyToJson(preKey));
    }
    root.insert(StorageKeys::OneTimePreKeys, preKeys);

    QJsonArray trustPins;
    for (const auto& pin : m_trustPins) {
        trustPins.push_back(trustPinToJson(pin));
    }
    root.insert(StorageKeys::TrustPins, trustPins);

    QJsonArray messages;
    for (const auto& message : m_messages) {
        messages.push_back(messageToJson(message));
    }
    root.insert(StorageKeys::Messages, messages);

    if (m_secretProtectionRequired) {
        const auto protectedRoot = protectSecrets(root);
        if (protectedRoot.failed()) {
            return Result<bool>::failure(protectedRoot.error());
        }
        root = protectedRoot.value();
    }

    QFile file(m_path);
    if (!file.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
        return Result<bool>::failure({ErrorCode::StorageError, QString("Could not write %1.").arg(m_path)});
    }
    file.write(QJsonDocument(root).toJson(QJsonDocument::Indented));
    return Result<bool>::success(true);
}

Result<QJsonObject> JsonLocalStore::protectSecrets(QJsonObject root) const {
    if (m_secretPassphrase.isEmpty()) {
        return Result<QJsonObject>::failure({ErrorCode::StorageError, "A local state passphrase is required before saving real-mode secrets."});
    }

    QByteArray salt = m_secretSalt;
    if (salt.isEmpty()) {
        salt = randomBytes(SecretSaltBytes);
    }
    if (salt.size() != SecretSaltBytes) {
        return Result<QJsonObject>::failure({ErrorCode::StorageError, "Could not create local state encryption salt."});
    }
    root.insert(SecretSaltKey, bytesToBase64(salt));

    if (root.contains("session")) {
        QJsonObject session = root.value("session").toObject();
        const auto sessionResult = protectStrings(session, {StorageKeys::AccessToken, StorageKeys::RefreshToken}, m_secretPassphrase, salt);
        if (sessionResult.failed()) {
            return Result<QJsonObject>::failure(sessionResult.error());
        }
        root.insert("session", session);
    }

    QJsonArray devices;
    for (const auto value : root.value(StorageKeys::DeviceKeys).toArray()) {
        QJsonObject device = value.toObject();
        const auto deviceResult = protectStrings(device, {
            StorageKeys::IdentityPrivateKey,
            StorageKeys::IdentitySigningPrivateKey,
            StorageKeys::SignedPreKeyPrivate
        }, m_secretPassphrase, salt);
        if (deviceResult.failed()) {
            return Result<QJsonObject>::failure(deviceResult.error());
        }
        devices.push_back(device);
    }
    root.insert(StorageKeys::DeviceKeys, devices);

    QJsonArray preKeys;
    for (const auto value : root.value(StorageKeys::OneTimePreKeys).toArray()) {
        QJsonObject preKey = value.toObject();
        const auto preKeyResult = protectString(preKey, StorageKeys::PreKeyPrivate, m_secretPassphrase, salt);
        if (preKeyResult.failed()) {
            return Result<QJsonObject>::failure(preKeyResult.error());
        }
        preKeys.push_back(preKey);
    }
    root.insert(StorageKeys::OneTimePreKeys, preKeys);

    QJsonArray trustPins;
    for (const auto value : root.value(StorageKeys::TrustPins).toArray()) {
        QJsonObject trustPin = value.toObject();
        const auto trustResult = protectString(trustPin, StorageKeys::IdentityKey, m_secretPassphrase, salt);
        if (trustResult.failed()) {
            return Result<QJsonObject>::failure(trustResult.error());
        }
        trustPins.push_back(trustPin);
    }
    root.insert(StorageKeys::TrustPins, trustPins);

    return Result<QJsonObject>::success(root);
}

Result<QJsonObject> JsonLocalStore::unprotectSecrets(QJsonObject root) const {
    if (m_secretPassphrase.isEmpty()) {
        return Result<QJsonObject>::failure({ErrorCode::StorageError, "A local state passphrase is required before loading real-mode secrets."});
    }
    if (m_secretSalt.size() != SecretSaltBytes) {
        return Result<QJsonObject>::failure({ErrorCode::StorageError, "Local state encryption salt is invalid."});
    }

    if (root.contains("session")) {
        QJsonObject session = root.value("session").toObject();
        const auto sessionResult = unprotectStrings(session, {StorageKeys::AccessToken, StorageKeys::RefreshToken}, m_secretPassphrase, m_secretSalt);
        if (sessionResult.failed()) {
            return Result<QJsonObject>::failure(sessionResult.error());
        }
        root.insert("session", session);
    }

    QJsonArray devices;
    for (const auto value : root.value(StorageKeys::DeviceKeys).toArray()) {
        QJsonObject device = value.toObject();
        const auto deviceResult = unprotectStrings(device, {
            StorageKeys::IdentityPrivateKey,
            StorageKeys::IdentitySigningPrivateKey,
            StorageKeys::SignedPreKeyPrivate
        }, m_secretPassphrase, m_secretSalt);
        if (deviceResult.failed()) {
            return Result<QJsonObject>::failure(deviceResult.error());
        }
        devices.push_back(device);
    }
    root.insert(StorageKeys::DeviceKeys, devices);

    QJsonArray preKeys;
    for (const auto value : root.value(StorageKeys::OneTimePreKeys).toArray()) {
        QJsonObject preKey = value.toObject();
        const auto preKeyResult = unprotectString(preKey, StorageKeys::PreKeyPrivate, m_secretPassphrase, m_secretSalt);
        if (preKeyResult.failed()) {
            return Result<QJsonObject>::failure(preKeyResult.error());
        }
        preKeys.push_back(preKey);
    }
    root.insert(StorageKeys::OneTimePreKeys, preKeys);

    QJsonArray trustPins;
    for (const auto value : root.value(StorageKeys::TrustPins).toArray()) {
        QJsonObject trustPin = value.toObject();
        const auto trustResult = unprotectString(trustPin, StorageKeys::IdentityKey, m_secretPassphrase, m_secretSalt);
        if (trustResult.failed()) {
            return Result<QJsonObject>::failure(trustResult.error());
        }
        trustPins.push_back(trustPin);
    }
    root.insert(StorageKeys::TrustPins, trustPins);

    return Result<QJsonObject>::success(root);
}
