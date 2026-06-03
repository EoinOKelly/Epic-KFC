#pragma once

#include "domain/Models.h"
#include "support/Result.h"

#include <QJsonObject>
#include <QString>

#include <set>
#include <vector>

class JsonLocalStore {
public:
    explicit JsonLocalStore(QString path, bool secretProtectionRequired = false);

    void setSecretProtectionRequired(bool required);
    void setSecretPassphrase(QString passphrase);
    void clearSecretPassphrase();
    Result<std::optional<QString>> lastAccountId() const;
    Result<bool> useAccountScopedPath(const QString& accountId, bool rememberAccount = true);
    Result<bool> reload();

    Result<bool> saveSession(const AuthSession& session);
    Result<std::optional<AuthSession>> loadSession() const;
    Result<bool> clearSession();

    Result<bool> saveDeviceKeys(const DeviceKeyMaterial& material);
    Result<std::optional<DeviceKeyMaterial>> loadDeviceKeys(int deviceId) const;
    Result<bool> saveOneTimePreKeys(const std::vector<OneTimePreKey>& preKeys);
    Result<std::vector<OneTimePreKey>> loadOneTimePreKeys(int deviceId) const;

    Result<bool> saveKnownUser(const UserAddress& address);
    Result<std::optional<KnownUser>> knownUser(const QString& userId, int deviceId) const;
    Result<bool> saveTrustPin(const TrustPin& pin);
    Result<std::optional<TrustPin>> trustPin(const QString& userId, int deviceId) const;

    Result<bool> saveMessage(const LocalMessage& message);
    Result<bool> markMessageDeletedFor(const QString& currentUserId, const QString& messageId);
    Result<bool> reconcileVisibleMessages(const QString& currentUserId, MessageDirection direction, const std::set<QString>& visibleMessageIds);
    Result<std::optional<LocalMessage>> findMessage(const QString& messageId) const;
    Result<MessageList> allMessages() const;
    Result<MessageList> messagesWithPeer(const QString& currentUserId, const QString& peerUserId) const;
    Result<ConversationList> conversationsFor(const QString& currentUserId) const;
    Result<ConversationList> unreadConversationsFor(const QString& currentUserId) const;
    Result<bool> markConversationRead(const QString& currentUserId, const QString& peerUserId);

private:
    Result<bool> load();
    Result<bool> save() const;
    Result<bool> rememberLastAccountId(const QString& accountId) const;
    Result<QJsonObject> protectSecrets(QJsonObject root) const;
    Result<QJsonObject> unprotectSecrets(QJsonObject root) const;

    QString m_indexPath;
    QString m_path;
    bool m_secretProtectionRequired{false};
    QString m_secretPassphrase;
    QByteArray m_secretSalt;
    AuthSession m_session;
    bool m_hasSession{false};
    std::vector<DeviceKeyMaterial> m_deviceKeys;
    std::vector<OneTimePreKey> m_oneTimePreKeys;
    std::vector<KnownUser> m_knownUsers;
    std::vector<TrustPin> m_trustPins;
    MessageList m_messages;
};
