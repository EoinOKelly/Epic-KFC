#pragma once

#include "gateways/Gateways.h"

#include <QJsonDocument>
#include <QJsonObject>
#include <QNetworkAccessManager>
#include <QUrl>

class HttpClient : public QObject {
    Q_OBJECT

public:
    explicit HttpClient(QString baseUrl, QObject* parent = nullptr);

    void get(const QString& path, const QString& accessToken, GatewayCallback<QJsonDocument> callback);
    void post(const QString& path, const QString& accessToken, const QJsonObject& body, GatewayCallback<QJsonDocument> callback);
    void put(const QString& path, const QString& accessToken, const QJsonObject& body, GatewayCallback<QJsonDocument> callback);
    void deleteResource(const QString& path, const QString& accessToken, GatewayCallback<QJsonDocument> callback);

private:
    void send(const QString& method, const QString& path, const QString& accessToken, const QJsonObject* body, GatewayCallback<QJsonDocument> callback);
    QUrl urlFor(const QString& path) const;
    QNetworkRequest requestFor(const QString& path, const QString& accessToken) const;
    ClientError errorForReply(QNetworkReply& reply, const QByteArray& responseBody) const;

    QUrl m_baseUrl;
    QNetworkAccessManager m_network;
};

class HttpAuthGateway : public QObject, public IAuthGateway {
    Q_OBJECT

public:
    explicit HttpAuthGateway(HttpClient& client, QObject* parent = nullptr);

    void registerUser(const QString& username, const QString& email, const QString& password, GatewayCallback<UserProfile> callback) override;
    void login(const QString& usernameOrEmail, const QString& password, GatewayCallback<AuthSession> callback) override;
    void currentUser(const QString& accessToken, GatewayCallback<UserProfile> callback) override;
    void logout(const QString& refreshToken, GatewayCallback<bool> callback) override;

private:
    UserProfile userFromJson(const QJsonObject& object) const;
    TokenSet tokensFromJson(const QJsonObject& object) const;

    HttpClient& m_client;
};

class HttpKeyGateway : public QObject, public IKeyGateway {
    Q_OBJECT

public:
    explicit HttpKeyGateway(HttpClient& client, QObject* parent = nullptr);

    void upsertDeviceKeys(const QString& accessToken, const DeviceKeyMaterial& material, GatewayCallback<bool> callback) override;
    void uploadOneTimePreKeys(const QString& accessToken, int deviceId, const QList<OneTimePreKey>& preKeys, GatewayCallback<bool> callback) override;
    void fetchPreKeyBundle(const QString& accessToken, const QString& userId, int deviceId, GatewayCallback<PreKeyBundle> callback) override;

private:
    HttpClient& m_client;
};

class HttpMessageGateway : public QObject, public IMessageGateway {
    Q_OBJECT

public:
    explicit HttpMessageGateway(HttpClient& client, QObject* parent = nullptr);

    void sendMessage(const QString& accessToken, const LocalMessage& draft, std::optional<int> consumedPreKeyId, GatewayCallback<LocalMessage> callback) override;
    void listReceived(const QString& accessToken, GatewayCallback<MessageList> callback) override;
    void listSent(const QString& accessToken, GatewayCallback<MessageList> callback) override;
    void getMessage(const QString& accessToken, const QString& messageId, GatewayCallback<LocalMessage> callback) override;
    void forwardMessage(const QString& accessToken, const QString& originalMessageId, const LocalMessage& draft, std::optional<int> consumedPreKeyId, GatewayCallback<LocalMessage> callback) override;
    void revokeMessage(const QString& accessToken, const QString& messageId, GatewayCallback<LocalMessage> callback) override;
    void deleteMessage(const QString& accessToken, const QString& messageId, GatewayCallback<bool> callback) override;

private:
    QJsonObject sendBodyFor(const LocalMessage& draft, std::optional<int> consumedPreKeyId) const;
    LocalMessage messageFromJson(const QJsonObject& object, MessageDirection direction) const;
    MessageList messageListFromJson(const QJsonArray& array, MessageDirection direction) const;

    HttpClient& m_client;
};
