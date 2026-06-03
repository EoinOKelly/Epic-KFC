#pragma once

#include "app/EventBus.h"
#include "crypto/NativeSignalCryptoProvider.h"
#include "gateways/Gateways.h"
#include "storage/JsonLocalStore.h"

#include <QObject>

#include <set>

class SessionService : public QObject {
    Q_OBJECT

public:
    SessionService(EventBus& events, IAuthGateway& authGateway, JsonLocalStore& store, bool accountScopedState = false, QObject* parent = nullptr);

    void registerUser(const QString& username, const QString& email, const QString& password);
    void login(const QString& usernameOrEmail, const QString& password);
    void logout();
    bool isLoggedIn() const;
    std::optional<AuthSession> currentSession() const;
    QString accessToken() const;
    QString currentUserId() const;
    void updateTokens(const TokenSet& tokens);

private:
    EventBus& m_events;
    IAuthGateway& m_authGateway;
    JsonLocalStore& m_store;
    bool m_accountScopedState{false};
    std::optional<AuthSession> m_session;
};

class KeyService : public QObject {
    Q_OBJECT

public:
    KeyService(EventBus& events, IKeyGateway& keyGateway, IUserDirectoryGateway& userDirectoryGateway, ICryptoProvider& cryptoProvider, JsonLocalStore& store, SessionService& sessionService, int deviceId, QObject* parent = nullptr);

    void ensureDeviceKeysUploaded();
    void trustUsername(const QString& username);
    Result<DeviceKeyMaterial> currentDevice();
    Result<std::optional<TrustPin>> trustPin(const QString& userId, int deviceId) const;
    Result<PreKeyBundle> cachedBundle(const QString& userId, int deviceId) const;
    void trustedBundle(const QString& userId, int deviceId, GatewayCallback<PreKeyBundle> callback);

private:
    void uploadOneTimePreKeys();

    EventBus& m_events;
    IKeyGateway& m_keyGateway;
    IUserDirectoryGateway& m_userDirectoryGateway;
    ICryptoProvider& m_cryptoProvider;
    JsonLocalStore& m_store;
    SessionService& m_sessionService;
    int m_deviceId;
    std::optional<PreKeyBundle> m_lastTrustedBundle;
};

class MessageService : public QObject {
    Q_OBJECT

public:
    MessageService(EventBus& events, IMessageGateway& messageGateway, IUserDirectoryGateway& userDirectoryGateway, ICryptoProvider& cryptoProvider, JsonLocalStore& store, SessionService& sessionService, KeyService& keyService, int deviceId, QObject* parent = nullptr);

    void listReceived();
    void listSent();
    void listConversations();
    void listUnreadSenders();
    void send(const QString& recipientUsername, const QString& plaintext);
    void readConversation(const QString& username, int page);
    void forward(const QString& messageId, const QString& recipientUsername);
    void revoke(const QString& messageId);
    void deleteMessage(const QString& messageId);
    void download(const QString& messageId, const QString& path);
    void verify(const QString& messageId);

private:
    bool requireSession();
    std::optional<OneTimePreKey> oneTimePreKeyFor(const LocalMessage& message) const;
    void saveMessages(const MessageList& messages);
    void saveAndReconcileMessages(const MessageList& messages, MessageDirection direction);
    void openConversationFromCache(const UserAddress& address, const QString& username, int page);
    void sendToAddress(const UserAddress& recipientAddress, const QString& plaintext);
    void forwardToAddress(const QString& messageId, const UserAddress& recipientAddress);
    PreKeyBundle selfPreKeyBundleFor(const DeviceKeyMaterial& device) const;
    Result<QString> createLocalSenderCopy(const DeviceKeyMaterial& device, const QString& plaintext);
    Result<QString> decryptForCurrentUser(const DeviceKeyMaterial& device, const LocalMessage& message);
    LocalMessage draftFor(const QString& recipientUserId, int recipientDeviceId, const QString& wirePayloadJson) const;
    void verifyPublicAnchor(const QString& messageId, const BlockchainAnchor& anchor);

    EventBus& m_events;
    IMessageGateway& m_messageGateway;
    IUserDirectoryGateway& m_userDirectoryGateway;
    ICryptoProvider& m_cryptoProvider;
    JsonLocalStore& m_store;
    SessionService& m_sessionService;
    KeyService& m_keyService;
    int m_deviceId;
};
