#include "gateways/Gateways.h"

#include "support/ClientConstants.h"

#include <QDateTime>
#include <QTimer>
#include <QUuid>

#include <algorithm>

namespace {
constexpr int MockLatencyMs = 10;

QString mockTokenFor(const QString& username) {
    return QString("mock-token-%1").arg(username);
}

QString bundleKey(const QString& userId, int deviceId) {
    return QString("%1:%2").arg(userId).arg(deviceId);
}

void later(QObject* parent, std::function<void()> work) {
    QTimer::singleShot(MockLatencyMs, parent, std::move(work));
}
}

MockAuthGateway::MockAuthGateway(QObject* parent)
    : QObject(parent) {
}

void MockAuthGateway::registerUser(const QString& username, const QString& email, const QString& password, GatewayCallback<UserProfile> callback) {
    later(this, [username, email, password, callback = std::move(callback)]() mutable {
        if (username.trimmed().isEmpty() || email.trimmed().isEmpty() || password.isEmpty()) {
            callback(Result<UserProfile>::failure({ErrorCode::InvalidCommand, "Username, email, and password are required."}));
            return;
        }
        callback(Result<UserProfile>::success({QUuid::createUuid().toString(QUuid::WithoutBraces), username.trimmed(), email.trimmed()}));
    });
}

void MockAuthGateway::login(const QString& usernameOrEmail, const QString& password, GatewayCallback<AuthSession> callback) {
    later(this, [usernameOrEmail, password, callback = std::move(callback)]() mutable {
        if (usernameOrEmail.trimmed().isEmpty() || password.isEmpty()) {
            callback(Result<AuthSession>::failure({ErrorCode::InvalidCommand, "Login identifier and password are required."}));
            return;
        }
        const UserProfile user{QString("mock-user-%1").arg(usernameOrEmail.trimmed()), usernameOrEmail.trimmed(), QString("%1@example.test").arg(usernameOrEmail.trimmed())};
        const TokenSet tokens{mockTokenFor(usernameOrEmail), QString("mock-refresh-%1").arg(usernameOrEmail), "bearer", 3600};
        callback(Result<AuthSession>::success({user, tokens}));
    });
}

void MockAuthGateway::currentUser(const QString& accessToken, GatewayCallback<UserProfile> callback) {
    later(this, [accessToken, callback = std::move(callback)]() mutable {
        if (accessToken.isEmpty()) {
            callback(Result<UserProfile>::failure({ErrorCode::AuthRequired, AppText::AuthRequired}));
            return;
        }
        callback(Result<UserProfile>::success({"mock-user", "mock-user", "mock@example.test"}));
    });
}

void MockAuthGateway::logout(const QString& refreshToken, GatewayCallback<bool> callback) {
    later(this, [refreshToken, callback = std::move(callback)]() mutable {
        Q_UNUSED(refreshToken)
        callback(Result<bool>::success(true));
    });
}

MockKeyGateway::MockKeyGateway(QObject* parent)
    : QObject(parent) {
}

void MockKeyGateway::upsertDeviceKeys(const QString& accessToken, const DeviceKeyMaterial& material, GatewayCallback<bool> callback) {
    later(this, [this, accessToken, material, callback = std::move(callback)]() mutable {
        if (accessToken.isEmpty()) {
            callback(Result<bool>::failure({ErrorCode::AuthRequired, AppText::AuthRequired}));
            return;
        }

        const QString userId = "mock-user";
        m_bundles.insert(bundleKey(userId, material.deviceId), {
            userId,
            material.registrationId,
            material.deviceId,
            material.identityKey,
            material.identitySigningKey,
            material.signedPreKeyId,
            material.signedPreKey,
            material.signedPreKeySignature,
            std::nullopt,
            {}
        });
        callback(Result<bool>::success(true));
    });
}

void MockKeyGateway::uploadOneTimePreKeys(const QString& accessToken, int deviceId, const QList<OneTimePreKey>& preKeys, GatewayCallback<bool> callback) {
    later(this, [accessToken, deviceId, preKeys, callback = std::move(callback)]() mutable {
        Q_UNUSED(deviceId)
        Q_UNUSED(preKeys)
        if (accessToken.isEmpty()) {
            callback(Result<bool>::failure({ErrorCode::AuthRequired, AppText::AuthRequired}));
            return;
        }
        callback(Result<bool>::success(true));
    });
}

void MockKeyGateway::fetchPreKeyBundle(const QString& accessToken, const QString& userId, int deviceId, GatewayCallback<PreKeyBundle> callback) {
    later(this, [this, accessToken, userId, deviceId, callback = std::move(callback)]() mutable {
        if (accessToken.isEmpty()) {
            callback(Result<PreKeyBundle>::failure({ErrorCode::AuthRequired, AppText::AuthRequired}));
            return;
        }

        const QString key = bundleKey(userId, deviceId);
        if (m_bundles.contains(key)) {
            callback(Result<PreKeyBundle>::success(m_bundles.value(key)));
            return;
        }

        callback(Result<PreKeyBundle>::success({
            userId,
            12345,
            deviceId,
            QByteArray("mock-identity-key-000000000000").toBase64(),
            QByteArray("mock-signing-key-0000000000000").toBase64(),
            1,
            QByteArray("mock-signed-pre-key-00000000").toBase64(),
            QByteArray("mock-signature").toBase64(),
            1,
            QByteArray("mock-one-time-pre-key-00000").toBase64()
        }));
    });
}

MockUserDirectoryGateway::MockUserDirectoryGateway(QObject* parent)
    : QObject(parent) {
}

void MockUserDirectoryGateway::resolveUsername(const QString& accessToken, const QString& username, int defaultDeviceId, GatewayCallback<UserAddress> callback) {
    later(this, [accessToken, username, defaultDeviceId, callback = std::move(callback)]() mutable {
        const QString trimmedUsername = username.trimmed();
        if (accessToken.isEmpty()) {
            callback(Result<UserAddress>::failure({ErrorCode::AuthRequired, AppText::AuthRequired}));
            return;
        }
        if (trimmedUsername.isEmpty()) {
            callback(Result<UserAddress>::failure({ErrorCode::InvalidCommand, AppText::EmptyUsername}));
            return;
        }
        callback(Result<UserAddress>::success({
            QString("mock-user-%1").arg(trimmedUsername),
            trimmedUsername,
            defaultDeviceId
        }));
    });
}

MockMessageGateway::MockMessageGateway(QObject* parent)
    : QObject(parent) {
}

void MockMessageGateway::sendMessage(const QString& accessToken, const LocalMessage& draft, std::optional<int> consumedPreKeyId, GatewayCallback<LocalMessage> callback) {
    later(this, [this, accessToken, draft, consumedPreKeyId, callback = std::move(callback)]() mutable {
        Q_UNUSED(consumedPreKeyId)
        if (accessToken.isEmpty()) {
            callback(Result<LocalMessage>::failure({ErrorCode::AuthRequired, AppText::AuthRequired}));
            return;
        }
        LocalMessage saved = withServerFields(draft);
        saved.consumedOneTimePreKeyId = consumedPreKeyId;
        saved.direction = MessageDirection::Sent;
        m_messages.push_back(saved);
        callback(Result<LocalMessage>::success(saved));
    });
}

void MockMessageGateway::listReceived(const QString& accessToken, GatewayCallback<MessageList> callback) {
    later(this, [this, accessToken, callback = std::move(callback)]() mutable {
        if (accessToken.isEmpty()) {
            callback(Result<MessageList>::failure({ErrorCode::AuthRequired, AppText::AuthRequired}));
            return;
        }
        MessageList received;
        std::copy_if(m_messages.cbegin(), m_messages.cend(), std::back_inserter(received), [](const LocalMessage& message) {
            return message.direction == MessageDirection::Received;
        });
        callback(Result<MessageList>::success(received));
    });
}

void MockMessageGateway::listSent(const QString& accessToken, GatewayCallback<MessageList> callback) {
    later(this, [this, accessToken, callback = std::move(callback)]() mutable {
        if (accessToken.isEmpty()) {
            callback(Result<MessageList>::failure({ErrorCode::AuthRequired, AppText::AuthRequired}));
            return;
        }
        MessageList sent;
        std::copy_if(m_messages.cbegin(), m_messages.cend(), std::back_inserter(sent), [](const LocalMessage& message) {
            return message.direction == MessageDirection::Sent;
        });
        callback(Result<MessageList>::success(sent));
    });
}

void MockMessageGateway::getMessage(const QString& accessToken, const QString& messageId, GatewayCallback<LocalMessage> callback) {
    later(this, [this, accessToken, messageId, callback = std::move(callback)]() mutable {
        if (accessToken.isEmpty()) {
            callback(Result<LocalMessage>::failure({ErrorCode::AuthRequired, AppText::AuthRequired}));
            return;
        }
        const auto it = std::find_if(m_messages.cbegin(), m_messages.cend(), [&messageId](const LocalMessage& message) {
            return message.id == messageId;
        });
        if (it == m_messages.cend()) {
            callback(Result<LocalMessage>::failure({ErrorCode::NotFound, "Message not found."}));
            return;
        }
        callback(Result<LocalMessage>::success(*it));
    });
}

void MockMessageGateway::forwardMessage(const QString& accessToken, const QString& originalMessageId, const LocalMessage& draft, std::optional<int> consumedPreKeyId, GatewayCallback<LocalMessage> callback) {
    Q_UNUSED(originalMessageId)
    sendMessage(accessToken, draft, consumedPreKeyId, std::move(callback));
}

void MockMessageGateway::revokeMessage(const QString& accessToken, const QString& messageId, GatewayCallback<LocalMessage> callback) {
    later(this, [this, accessToken, messageId, callback = std::move(callback)]() mutable {
        if (accessToken.isEmpty()) {
            callback(Result<LocalMessage>::failure({ErrorCode::AuthRequired, AppText::AuthRequired}));
            return;
        }
        auto it = std::find_if(m_messages.begin(), m_messages.end(), [&messageId](const LocalMessage& message) {
            return message.id == messageId;
        });
        if (it == m_messages.end()) {
            callback(Result<LocalMessage>::failure({ErrorCode::NotFound, "Message not found."}));
            return;
        }
        it->accessRevokedAt = QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs);
        callback(Result<LocalMessage>::success(*it));
    });
}

void MockMessageGateway::deleteMessage(const QString& accessToken, const QString& messageId, GatewayCallback<bool> callback) {
    later(this, [this, accessToken, messageId, callback = std::move(callback)]() mutable {
        if (accessToken.isEmpty()) {
            callback(Result<bool>::failure({ErrorCode::AuthRequired, AppText::AuthRequired}));
            return;
        }
        auto it = std::find_if(m_messages.begin(), m_messages.end(), [&messageId](const LocalMessage& message) {
            return message.id == messageId;
        });
        if (it == m_messages.end()) {
            callback(Result<bool>::failure({ErrorCode::NotFound, "Message not found."}));
            return;
        }
        it->deletedAt = QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs);
        callback(Result<bool>::success(true));
    });
}

LocalMessage MockMessageGateway::withServerFields(LocalMessage draft) {
    draft.id = QString("mock-message-%1").arg(m_nextMessageNumber++);
    draft.createdAt = QDateTime::currentDateTimeUtc();
    return draft;
}
