#pragma once

#include "app/EventBus.h"
#include "crypto/NativeSignalCryptoProvider.h"
#include "gateways/Gateways.h"
#include "storage/JsonLocalStore.h"

#include <QObject>

class SessionService : public QObject {
    Q_OBJECT

public:
    SessionService(EventBus& events, IAuthGateway& authGateway, JsonLocalStore& store, QObject* parent = nullptr);

    void registerUser(const QString& username, const QString& email, const QString& password);
    void login(const QString& usernameOrEmail, const QString& password);
    void logout();
    bool isLoggedIn() const;
    std::optional<AuthSession> currentSession() const;
    QString accessToken() const;
    QString currentUserId() const;

private:
    EventBus& m_events;
    IAuthGateway& m_authGateway;
    JsonLocalStore& m_store;
    std::optional<AuthSession> m_session;
};

class KeyService : public QObject {
    Q_OBJECT

public:
    KeyService(EventBus& events, IKeyGateway& keyGateway, ICryptoProvider& cryptoProvider, JsonLocalStore& store, SessionService& sessionService, int deviceId, QObject* parent = nullptr);

    void ensureDeviceKeysUploaded();
    void trustUser(const QString& userId, int deviceId);
    Result<DeviceKeyMaterial> currentDevice();
    Result<std::optional<TrustPin>> trustPin(const QString& userId, int deviceId) const;
    Result<PreKeyBundle> cachedBundle(const QString& userId, int deviceId) const;

private:
    void uploadOneTimePreKeys();

    EventBus& m_events;
    IKeyGateway& m_keyGateway;
    ICryptoProvider& m_cryptoProvider;
    JsonLocalStore& m_store;
    SessionService& m_sessionService;
    int m_deviceId;
    std::optional<PreKeyBundle> m_lastTrustedBundle;
};

class MessageService : public QObject {
    Q_OBJECT

public:
    MessageService(EventBus& events, IMessageGateway& messageGateway, ICryptoProvider& cryptoProvider, JsonLocalStore& store, SessionService& sessionService, KeyService& keyService, int deviceId, QObject* parent = nullptr);

    void listReceived();
    void listSent();
    void listConversations();
    void send(const QString& recipientUserId, int recipientDeviceId, const QString& plaintext);
    void read(const QString& messageId);
    void forward(const QString& messageId, const QString& recipientUserId, int recipientDeviceId);
    void revoke(const QString& messageId);
    void deleteMessage(const QString& messageId);
    void download(const QString& messageId, const QString& path);
    void verify(const QString& messageId);

private:
    bool requireSession();
    void saveAndEmitList(const MessageList& messages);
    LocalMessage draftFor(const QString& recipientUserId, int recipientDeviceId, const QString& wirePayloadJson) const;

    EventBus& m_events;
    IMessageGateway& m_messageGateway;
    ICryptoProvider& m_cryptoProvider;
    JsonLocalStore& m_store;
    SessionService& m_sessionService;
    KeyService& m_keyService;
    int m_deviceId;
};
