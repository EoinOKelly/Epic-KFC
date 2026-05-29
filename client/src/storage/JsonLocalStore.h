#pragma once

#include "domain/Models.h"
#include "support/Result.h"

#include <QJsonObject>
#include <QString>

class JsonLocalStore {
public:
    explicit JsonLocalStore(QString path);

    Result<bool> saveSession(const AuthSession& session);
    Result<std::optional<AuthSession>> loadSession() const;
    Result<bool> clearSession();

    Result<bool> saveDeviceKeys(const DeviceKeyMaterial& material);
    Result<std::optional<DeviceKeyMaterial>> loadDeviceKeys(int deviceId) const;
    Result<bool> saveOneTimePreKeys(const QList<OneTimePreKey>& preKeys);
    Result<QList<OneTimePreKey>> loadOneTimePreKeys(int deviceId) const;

    Result<bool> saveTrustPin(const TrustPin& pin);
    Result<std::optional<TrustPin>> trustPin(const QString& userId, int deviceId) const;

    Result<bool> saveMessage(const LocalMessage& message);
    Result<std::optional<LocalMessage>> findMessage(const QString& messageId) const;
    Result<MessageList> allMessages() const;
    Result<ConversationList> conversationsFor(const QString& currentUserId) const;

private:
    Result<bool> load();
    Result<bool> save() const;

    QString m_path;
    AuthSession m_session;
    bool m_hasSession{false};
    QList<DeviceKeyMaterial> m_deviceKeys;
    QList<OneTimePreKey> m_oneTimePreKeys;
    QList<TrustPin> m_trustPins;
    MessageList m_messages;
};
