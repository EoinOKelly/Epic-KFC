#pragma once

#include "domain/Models.h"
#include "support/Result.h"

#include <QJsonObject>
#include <QString>

#include <vector>

class JsonLocalStore {
public:
    explicit JsonLocalStore(QString path, bool secretProtectionRequired = false);

    void setSecretProtectionRequired(bool required);
    void setSecretPassphrase(QString passphrase);
    void clearSecretPassphrase();
    Result<bool> reload();

    Result<bool> saveSession(const AuthSession& session);
    Result<std::optional<AuthSession>> loadSession() const;
    Result<bool> clearSession();

    Result<bool> saveDeviceKeys(const DeviceKeyMaterial& material);
    Result<std::optional<DeviceKeyMaterial>> loadDeviceKeys(int deviceId) const;
    Result<bool> saveOneTimePreKeys(const std::vector<OneTimePreKey>& preKeys);
    Result<std::vector<OneTimePreKey>> loadOneTimePreKeys(int deviceId) const;

    Result<bool> saveTrustPin(const TrustPin& pin);
    Result<std::optional<TrustPin>> trustPin(const QString& userId, int deviceId) const;

    Result<bool> saveMessage(const LocalMessage& message);
    Result<std::optional<LocalMessage>> findMessage(const QString& messageId) const;
    Result<MessageList> allMessages() const;
    Result<ConversationList> conversationsFor(const QString& currentUserId) const;

private:
    Result<bool> load();
    Result<bool> save() const;
    Result<QJsonObject> protectSecrets(QJsonObject root) const;
    Result<QJsonObject> unprotectSecrets(QJsonObject root) const;

    QString m_path;
    bool m_secretProtectionRequired{false};
    QString m_secretPassphrase;
    QByteArray m_secretSalt;
    AuthSession m_session;
    bool m_hasSession{false};
    std::vector<DeviceKeyMaterial> m_deviceKeys;
    std::vector<OneTimePreKey> m_oneTimePreKeys;
    std::vector<TrustPin> m_trustPins;
    MessageList m_messages;
};
