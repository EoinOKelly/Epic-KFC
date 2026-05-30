#pragma once

#include "domain/Models.h"
#include "support/Result.h"

#include <QObject>

#include <functional>
#include <map>
#include <vector>

template <typename T>
using GatewayCallback = std::function<void(Result<T>)>;

class IAuthGateway {
public:
    virtual ~IAuthGateway() = default;
    virtual void registerUser(const QString& username, const QString& email, const QString& password, GatewayCallback<UserProfile> callback) = 0;
    virtual void login(const QString& usernameOrEmail, const QString& password, GatewayCallback<AuthSession> callback) = 0;
    virtual void currentUser(const QString& accessToken, GatewayCallback<UserProfile> callback) = 0;
    virtual void logout(const QString& refreshToken, GatewayCallback<bool> callback) = 0;
};

class IKeyGateway {
public:
    virtual ~IKeyGateway() = default;
    virtual void upsertDeviceKeys(const QString& accessToken, const DeviceKeyMaterial& material, GatewayCallback<bool> callback) = 0;
    virtual void uploadOneTimePreKeys(const QString& accessToken, int deviceId, const std::vector<OneTimePreKey>& preKeys, GatewayCallback<bool> callback) = 0;
    virtual void fetchPreKeyBundle(const QString& accessToken, const QString& userId, int deviceId, GatewayCallback<PreKeyBundle> callback) = 0;
};

class IUserDirectoryGateway {
public:
    virtual ~IUserDirectoryGateway() = default;
    virtual void resolveUsername(const QString& accessToken, const QString& username, int defaultDeviceId, GatewayCallback<UserAddress> callback) = 0;
};

class IMessageGateway {
public:
    virtual ~IMessageGateway() = default;
    virtual void sendMessage(const QString& accessToken, const LocalMessage& draft, std::optional<int> consumedPreKeyId, GatewayCallback<LocalMessage> callback) = 0;
    virtual void listReceived(const QString& accessToken, GatewayCallback<MessageList> callback) = 0;
    virtual void listSent(const QString& accessToken, GatewayCallback<MessageList> callback) = 0;
    virtual void getMessage(const QString& accessToken, const QString& messageId, GatewayCallback<LocalMessage> callback) = 0;
    virtual void forwardMessage(const QString& accessToken, const QString& originalMessageId, const LocalMessage& draft, std::optional<int> consumedPreKeyId, GatewayCallback<LocalMessage> callback) = 0;
    virtual void revokeMessage(const QString& accessToken, const QString& messageId, GatewayCallback<LocalMessage> callback) = 0;
    virtual void deleteMessage(const QString& accessToken, const QString& messageId, GatewayCallback<bool> callback) = 0;
};

class ICryptoProvider {
public:
    virtual ~ICryptoProvider() = default;
    virtual Result<DeviceKeyMaterial> loadOrCreateDevice(DeviceKeyMaterial existing, int deviceId) = 0;
    virtual Result<std::vector<OneTimePreKey>> createOneTimePreKeys(int deviceId, int count) = 0;
    virtual Result<bool> verifySignedPreKey(const PreKeyBundle& bundle) = 0;
    virtual Result<EncryptedPayload> encrypt(const QString& senderUserId, const DeviceKeyMaterial& senderDevice, const PreKeyBundle& recipientBundle, const QString& plaintext) = 0;
    virtual Result<QString> decrypt(const QString& currentUserId, const DeviceKeyMaterial& currentDevice, const LocalMessage& message, const std::optional<OneTimePreKey>& oneTimePreKey) = 0;
};

class MockAuthGateway : public QObject, public IAuthGateway {
    Q_OBJECT

public:
    explicit MockAuthGateway(QObject* parent = nullptr);

    void registerUser(const QString& username, const QString& email, const QString& password, GatewayCallback<UserProfile> callback) override;
    void login(const QString& usernameOrEmail, const QString& password, GatewayCallback<AuthSession> callback) override;
    void currentUser(const QString& accessToken, GatewayCallback<UserProfile> callback) override;
    void logout(const QString& refreshToken, GatewayCallback<bool> callback) override;
};

class MockKeyGateway : public QObject, public IKeyGateway {
    Q_OBJECT

public:
    explicit MockKeyGateway(QObject* parent = nullptr);

    void upsertDeviceKeys(const QString& accessToken, const DeviceKeyMaterial& material, GatewayCallback<bool> callback) override;
    void uploadOneTimePreKeys(const QString& accessToken, int deviceId, const std::vector<OneTimePreKey>& preKeys, GatewayCallback<bool> callback) override;
    void fetchPreKeyBundle(const QString& accessToken, const QString& userId, int deviceId, GatewayCallback<PreKeyBundle> callback) override;

private:
    std::map<QString, PreKeyBundle> m_bundles;
};

class MockUserDirectoryGateway : public QObject, public IUserDirectoryGateway {
    Q_OBJECT

public:
    explicit MockUserDirectoryGateway(QObject* parent = nullptr);

    void resolveUsername(const QString& accessToken, const QString& username, int defaultDeviceId, GatewayCallback<UserAddress> callback) override;
};

class MockMessageGateway : public QObject, public IMessageGateway {
    Q_OBJECT

public:
    explicit MockMessageGateway(QObject* parent = nullptr);

    void sendMessage(const QString& accessToken, const LocalMessage& draft, std::optional<int> consumedPreKeyId, GatewayCallback<LocalMessage> callback) override;
    void listReceived(const QString& accessToken, GatewayCallback<MessageList> callback) override;
    void listSent(const QString& accessToken, GatewayCallback<MessageList> callback) override;
    void getMessage(const QString& accessToken, const QString& messageId, GatewayCallback<LocalMessage> callback) override;
    void forwardMessage(const QString& accessToken, const QString& originalMessageId, const LocalMessage& draft, std::optional<int> consumedPreKeyId, GatewayCallback<LocalMessage> callback) override;
    void revokeMessage(const QString& accessToken, const QString& messageId, GatewayCallback<LocalMessage> callback) override;
    void deleteMessage(const QString& accessToken, const QString& messageId, GatewayCallback<bool> callback) override;

private:
    LocalMessage withServerFields(LocalMessage draft);

    MessageList m_messages;
    int m_nextMessageNumber{1};
};
