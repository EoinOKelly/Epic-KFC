#include "storage/JsonLocalStore.h"

#include "support/ClientConstants.h"

#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>

#include <algorithm>
#include <utility>

namespace {
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
}

JsonLocalStore::JsonLocalStore(QString path)
    : m_path(std::move(path)) {
    load();
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

Result<bool> JsonLocalStore::saveOneTimePreKeys(const QList<OneTimePreKey>& preKeys) {
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

Result<QList<OneTimePreKey>> JsonLocalStore::loadOneTimePreKeys(int deviceId) const {
    QList<OneTimePreKey> matching;
    std::copy_if(m_oneTimePreKeys.cbegin(), m_oneTimePreKeys.cend(), std::back_inserter(matching), [deviceId](const OneTimePreKey& preKey) {
        return preKey.deviceId == deviceId;
    });
    return Result<QList<OneTimePreKey>>::success(matching);
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
    QHash<QString, ConversationSummary> summaries;
    for (const auto& message : m_messages) {
        const bool sentByCurrentUser = message.senderUserId == currentUserId;
        const QString peerUserId = sentByCurrentUser ? message.recipientUserId : message.senderUserId;
        const int peerDeviceId = sentByCurrentUser ? message.recipientDeviceId : message.senderDeviceId;
        const QString key = QString("%1:%2").arg(peerUserId).arg(peerDeviceId);
        auto summary = summaries.value(key, {peerUserId, peerDeviceId, 0, {}});
        summary.messageCount += 1;
        if (!summary.latestMessageAt.isValid() || message.createdAt > summary.latestMessageAt) {
            summary.latestMessageAt = message.createdAt;
        }
        summaries.insert(key, summary);
    }
    return Result<ConversationList>::success(summaries.values());
}

Result<bool> JsonLocalStore::load() {
    QFile file(m_path);
    if (!file.exists()) {
        return Result<bool>::success(true);
    }
    if (!file.open(QIODevice::ReadOnly)) {
        return Result<bool>::failure({ErrorCode::StorageError, QString("Could not read %1.").arg(m_path)});
    }

    const QJsonObject root = QJsonDocument::fromJson(file.readAll()).object();
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

    QFile file(m_path);
    if (!file.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
        return Result<bool>::failure({ErrorCode::StorageError, QString("Could not write %1.").arg(m_path)});
    }
    file.write(QJsonDocument(root).toJson(QJsonDocument::Indented));
    return Result<bool>::success(true);
}
