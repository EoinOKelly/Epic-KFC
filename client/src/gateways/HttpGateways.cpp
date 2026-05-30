#include "gateways/HttpGateways.h"

#include "support/ClientConstants.h"

#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QUuid>

#include <algorithm>
#include <utility>

namespace {
QString withoutTrailingSlash(QString value) {
    while (value.endsWith('/')) {
        value.chop(1);
    }
    return value;
}

QString normalizedPath(QString path) {
    if (!path.startsWith('/')) {
        path.prepend('/');
    }
    return path;
}

QString authPath(const QString& suffix) {
    return QString("/auth%1").arg(suffix);
}

QString keyPath(const QString& suffix) {
    return QString("/keys%1").arg(suffix);
}

QString messagePath(const QString& suffix) {
    return QString("/messages%1").arg(suffix);
}

QString userPath(const QString& suffix) {
    return QString("/users%1").arg(suffix);
}

QString encodedPathSegment(const QString& value) {
    return QString::fromLatin1(QUrl::toPercentEncoding(value));
}

void addOptionalString(QJsonObject& object, const QString& key, const QString& value) {
    if (value.isEmpty()) {
        object.insert(key, QJsonValue::Null);
        return;
    }
    object.insert(key, value);
}

bool isRefreshPath(const QString& path) {
    return normalizedPath(path) == authPath("/refresh");
}
}

HttpClient::HttpClient(QString baseUrl, QObject* parent)
    : QObject(parent)
    , m_baseUrl(withoutTrailingSlash(std::move(baseUrl))) {
    QString path = withoutTrailingSlash(m_baseUrl.path());
    if (path.endsWith(AppText::ApiPrefix)) {
        m_baseUrl.setPath(path);
    }
}

void HttpClient::get(const QString& path, const QString& accessToken, GatewayCallback<QJsonDocument> callback) {
    send("GET", path, accessToken, std::nullopt, std::move(callback));
}

void HttpClient::post(const QString& path, const QString& accessToken, const QJsonObject& body, GatewayCallback<QJsonDocument> callback) {
    send("POST", path, accessToken, body, std::move(callback));
}

void HttpClient::put(const QString& path, const QString& accessToken, const QJsonObject& body, GatewayCallback<QJsonDocument> callback) {
    send("PUT", path, accessToken, body, std::move(callback));
}

void HttpClient::deleteResource(const QString& path, const QString& accessToken, GatewayCallback<QJsonDocument> callback) {
    send("DELETE", path, accessToken, std::nullopt, std::move(callback));
}

void HttpClient::setTokens(const TokenSet& tokens) {
    m_tokens = tokens;
}

void HttpClient::clearTokens() {
    m_tokens = {};
}

void HttpClient::setTokenUpdateHandler(std::function<void(const TokenSet&)> handler) {
    m_tokenUpdateHandler = std::move(handler);
}

void HttpClient::send(const QString& method, const QString& path, const QString& accessToken, std::optional<QJsonObject> body, GatewayCallback<QJsonDocument> callback, bool alreadyRetried) {
    QNetworkReply* reply = nullptr;
    QNetworkRequest request = requestFor(path, accessToken);
    const QByteArray payload = body.has_value() ? QJsonDocument(*body).toJson(QJsonDocument::Compact) : QByteArray();

    if (method == "GET") {
        reply = m_network.get(request);
    } else if (method == "POST") {
        reply = m_network.post(request, payload);
    } else if (method == "PUT") {
        reply = m_network.put(request, payload);
    } else if (method == "DELETE") {
        reply = m_network.deleteResource(request);
    }

    QObject::connect(reply, &QNetworkReply::sslErrors, reply, [](const QList<QSslError>& errors) {
        Q_UNUSED(errors)
    });

    QObject::connect(reply, &QNetworkReply::finished, reply, [this, reply, method, path, accessToken, body, alreadyRetried, callback = std::move(callback)]() mutable {
        const QByteArray responseBody = reply->readAll();
        if (reply->error() != QNetworkReply::NoError) {
            const int statusCode = reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();
            const bool canRefresh = statusCode == 401
                && !alreadyRetried
                && !m_tokens.refreshToken.isEmpty()
                && !isRefreshPath(path);
            if (canRefresh) {
                reply->deleteLater();
                refreshTokens([this, method, path, accessToken, body, callback = std::move(callback)](Result<TokenSet> refreshResult) mutable {
                    if (refreshResult.failed()) {
                        callback(Result<QJsonDocument>::failure(refreshResult.error()));
                        return;
                    }
                    const QString retryToken = accessToken.isEmpty() ? QString() : m_tokens.accessToken;
                    send(method, path, retryToken, body, std::move(callback), true);
                });
                return;
            }

            callback(Result<QJsonDocument>::failure(errorForReply(*reply, responseBody)));
            reply->deleteLater();
            return;
        }

        QJsonParseError parseError;
        const QJsonDocument document = QJsonDocument::fromJson(responseBody, &parseError);
        if (parseError.error != QJsonParseError::NoError && !responseBody.trimmed().isEmpty()) {
            callback(Result<QJsonDocument>::failure({ErrorCode::HttpError, parseError.errorString()}));
            reply->deleteLater();
            return;
        }

        callback(Result<QJsonDocument>::success(document));
        reply->deleteLater();
    });
}

void HttpClient::refreshTokens(GatewayCallback<TokenSet> callback) {
    const QString previousRefreshToken = m_tokens.refreshToken;
    send("POST", authPath("/refresh"), {}, QJsonObject{{"refresh_token", previousRefreshToken}}, [this, previousRefreshToken, callback = std::move(callback)](Result<QJsonDocument> result) mutable {
        if (result.failed()) {
            callback(Result<TokenSet>::failure(result.error()));
            return;
        }

        TokenSet tokens = tokensFromJson(result.value().object());
        if (tokens.refreshToken.isEmpty()) {
            tokens.refreshToken = previousRefreshToken;
        }
        m_tokens = tokens;
        if (m_tokenUpdateHandler) {
            m_tokenUpdateHandler(m_tokens);
        }
        callback(Result<TokenSet>::success(m_tokens));
    }, true);
}

TokenSet HttpClient::tokensFromJson(const QJsonObject& object) const {
    return {
        object.value("access_token").toString(),
        object.value("refresh_token").toString(),
        object.value("token_type").toString(),
        object.value("expires_in").toInt()
    };
}

QUrl HttpClient::urlFor(const QString& path) const {
    QUrl url = m_baseUrl;
    const QString basePath = withoutTrailingSlash(url.path());
    url.setPath(basePath + normalizedPath(path));
    return url;
}

QNetworkRequest HttpClient::requestFor(const QString& path, const QString& accessToken) const {
    QNetworkRequest request(urlFor(path));
    request.setHeader(QNetworkRequest::ContentTypeHeader, AppText::JsonContentType);
    const QString effectiveAccessToken = !accessToken.isEmpty() && !m_tokens.accessToken.isEmpty()
        ? m_tokens.accessToken
        : accessToken;
    if (!effectiveAccessToken.isEmpty()) {
        request.setRawHeader("Authorization", QString(AppText::BearerPrefix + effectiveAccessToken).toUtf8());
    }
    return request;
}

ClientError HttpClient::errorForReply(QNetworkReply& reply, const QByteArray& responseBody) const {
    const int statusCode = reply.attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();
    QString message = reply.errorString();
    const QJsonObject errorObject = QJsonDocument::fromJson(responseBody).object();
    if (errorObject.contains("detail")) {
        message = errorObject.value("detail").toString(message);
    }
    if (reply.error() == QNetworkReply::SslHandshakeFailedError) {
        return {ErrorCode::TlsError, message};
    }
    if (statusCode == 401) {
        return {ErrorCode::AuthRequired, QString("HTTP %1: %2").arg(statusCode).arg(message)};
    }
    if (statusCode > 0) {
        return {ErrorCode::HttpError, QString("HTTP %1: %2").arg(statusCode).arg(message)};
    }
    return {ErrorCode::NetworkError, message};
}

HttpAuthGateway::HttpAuthGateway(HttpClient& client, QObject* parent)
    : QObject(parent)
    , m_client(client) {
}

void HttpAuthGateway::registerUser(const QString& username, const QString& email, const QString& password, GatewayCallback<UserProfile> callback) {
    m_client.post(authPath("/register"), {}, {
        {"username", username},
        {"email", email},
        {"password", password}
    }, [this, callback = std::move(callback)](Result<QJsonDocument> result) mutable {
        if (result.failed()) {
            callback(Result<UserProfile>::failure(result.error()));
            return;
        }
        callback(Result<UserProfile>::success(userFromJson(result.value().object())));
    });
}

void HttpAuthGateway::login(const QString& usernameOrEmail, const QString& password, GatewayCallback<AuthSession> callback) {
    m_client.post(authPath("/login"), {}, {
        {"username_or_email", usernameOrEmail},
        {"password", password}
    }, [this, callback = std::move(callback)](Result<QJsonDocument> tokensResult) mutable {
        if (tokensResult.failed()) {
            callback(Result<AuthSession>::failure(tokensResult.error()));
            return;
        }

        const TokenSet tokens = tokensFromJson(tokensResult.value().object());
        m_client.setTokens(tokens);
        m_client.get(authPath("/me"), tokens.accessToken, [this, tokens, callback = std::move(callback)](Result<QJsonDocument> userResult) mutable {
            if (userResult.failed()) {
                callback(Result<AuthSession>::failure(userResult.error()));
                return;
            }
            callback(Result<AuthSession>::success({userFromJson(userResult.value().object()), tokens}));
        });
    });
}

void HttpAuthGateway::currentUser(const QString& accessToken, GatewayCallback<UserProfile> callback) {
    m_client.get(authPath("/me"), accessToken, [this, callback = std::move(callback)](Result<QJsonDocument> result) mutable {
        if (result.failed()) {
            callback(Result<UserProfile>::failure(result.error()));
            return;
        }
        callback(Result<UserProfile>::success(userFromJson(result.value().object())));
    });
}

void HttpAuthGateway::logout(const QString& refreshToken, GatewayCallback<bool> callback) {
    m_client.post(authPath("/logout"), {}, {{"refresh_token", refreshToken}}, [this, callback = std::move(callback)](Result<QJsonDocument> result) mutable {
        if (result.failed()) {
            callback(Result<bool>::failure(result.error()));
            return;
        }
        m_client.clearTokens();
        callback(Result<bool>::success(true));
    });
}

UserProfile HttpAuthGateway::userFromJson(const QJsonObject& object) const {
    return {
        object.value("id").toString(),
        object.value("username").toString(),
        object.value("email").toString()
    };
}

TokenSet HttpAuthGateway::tokensFromJson(const QJsonObject& object) const {
    return {
        object.value("access_token").toString(),
        object.value("refresh_token").toString(),
        object.value("token_type").toString(),
        object.value("expires_in").toInt()
    };
}

HttpKeyGateway::HttpKeyGateway(HttpClient& client, QObject* parent)
    : QObject(parent)
    , m_client(client) {
}

void HttpKeyGateway::upsertDeviceKeys(const QString& accessToken, const DeviceKeyMaterial& material, GatewayCallback<bool> callback) {
    const QString path = keyPath(QString("/devices/%1").arg(material.deviceId));
    m_client.put(path, accessToken, {
        {"device_id", material.deviceId},
        {"registration_id", material.registrationId},
        {"identity_key_public_b64", material.identityKey},
        {"identity_signing_public_b64", material.identitySigningKey},
        {"signed_prekey_id", material.signedPreKeyId},
        {"signed_prekey_public_b64", material.signedPreKey},
        {"signed_prekey_signature_b64", material.signedPreKeySignature}
    }, [callback = std::move(callback)](Result<QJsonDocument> result) mutable {
        if (result.failed()) {
            callback(Result<bool>::failure(result.error()));
            return;
        }
        callback(Result<bool>::success(true));
    });
}

void HttpKeyGateway::uploadOneTimePreKeys(const QString& accessToken, int deviceId, const QList<OneTimePreKey>& preKeys, GatewayCallback<bool> callback) {
    QJsonArray array;
    for (const auto& preKey : preKeys) {
        array.push_back(QJsonObject{
            {"device_id", preKey.deviceId},
            {"prekey_id", preKey.preKeyId},
            {"prekey_public_b64", preKey.publicKey}
        });
    }

    const QString path = keyPath(QString("/devices/%1/one-time-prekeys").arg(deviceId));
    m_client.post(path, accessToken, {{"prekeys", array}}, [callback = std::move(callback)](Result<QJsonDocument> result) mutable {
        if (result.failed()) {
            callback(Result<bool>::failure(result.error()));
            return;
        }
        callback(Result<bool>::success(true));
    });
}

void HttpKeyGateway::fetchPreKeyBundle(const QString& accessToken, const QString& userId, int deviceId, GatewayCallback<PreKeyBundle> callback) {
    const QString path = keyPath(QString("/users/%1/devices/%2/prekey-bundle").arg(userId).arg(deviceId));
    m_client.get(path, accessToken, [userId, callback = std::move(callback)](Result<QJsonDocument> result) mutable {
        if (result.failed()) {
            callback(Result<PreKeyBundle>::failure(result.error()));
            return;
        }
        const QJsonObject object = result.value().object();
        std::optional<int> oneTimePreKeyId;
        if (!object.value("oneTimePreKeyId").isNull() && !object.value("oneTimePreKeyId").isUndefined()) {
            oneTimePreKeyId = object.value("oneTimePreKeyId").toInt();
        }
        callback(Result<PreKeyBundle>::success({
            userId,
            object.value("registrationId").toInt(),
            object.value("deviceId").toInt(),
            object.value("identityKey").toString(),
            object.value("identitySigningKey").toString(),
            object.value("signedPreKeyId").toInt(),
            object.value("signedPreKey").toString(),
            object.value("signedPreKeySignature").toString(),
            oneTimePreKeyId,
            object.value("oneTimePreKey").toString()
        }));
    });
}

HttpUserDirectoryGateway::HttpUserDirectoryGateway(HttpClient& client, QObject* parent)
    : QObject(parent)
    , m_client(client) {
}

void HttpUserDirectoryGateway::resolveUsername(const QString& accessToken, const QString& username, int defaultDeviceId, GatewayCallback<UserAddress> callback) {
    const QString trimmedUsername = username.trimmed();
    if (trimmedUsername.isEmpty()) {
        callback(Result<UserAddress>::failure({ErrorCode::InvalidCommand, AppText::EmptyUsername}));
        return;
    }

    const bool isUuid = !QUuid(trimmedUsername).isNull();
    if (isUuid) {
        callback(Result<UserAddress>::success({trimmedUsername, trimmedUsername, defaultDeviceId}));
        return;
    }

    const QString path = userPath(QString("/by-username/%1").arg(encodedPathSegment(trimmedUsername)));
    m_client.get(path, accessToken, [this, trimmedUsername, defaultDeviceId, callback = std::move(callback)](Result<QJsonDocument> result) mutable {
        if (result.failed()) {
            callback(Result<UserAddress>::failure({result.error().code, AppText::UsernameResolveUnavailable}));
            return;
        }
        UserAddress address = userAddressFromJson(result.value().object(), defaultDeviceId);
        if (address.userId.isEmpty()) {
            callback(Result<UserAddress>::failure({ErrorCode::NotFound, QString("No user found for username %1.").arg(trimmedUsername)}));
            return;
        }
        callback(Result<UserAddress>::success(address));
    });
}

UserAddress HttpUserDirectoryGateway::userAddressFromJson(const QJsonObject& object, int defaultDeviceId) const {
    int deviceId = object.value("default_device_id").toInt(defaultDeviceId);
    const QJsonArray devices = object.value("devices").toArray();
    if (!devices.isEmpty()) {
        const auto activeDevice = std::find_if(devices.cbegin(), devices.cend(), [](const QJsonValue& value) {
            return value.toObject().value("is_active").toBool(true);
        });
        const QJsonObject device = activeDevice == devices.cend()
            ? devices.first().toObject()
            : (*activeDevice).toObject();
        deviceId = device.value("device_id").toInt(deviceId);
    }

    return {
        object.value("id").toString(object.value("user_id").toString()),
        object.value("username").toString(),
        deviceId
    };
}

HttpMessageGateway::HttpMessageGateway(HttpClient& client, QObject* parent)
    : QObject(parent)
    , m_client(client) {
}

void HttpMessageGateway::sendMessage(const QString& accessToken, const LocalMessage& draft, std::optional<int> consumedPreKeyId, GatewayCallback<LocalMessage> callback) {
    m_client.post(messagePath(""), accessToken, sendBodyFor(draft, consumedPreKeyId), [this, callback = std::move(callback)](Result<QJsonDocument> result) mutable {
        if (result.failed()) {
            callback(Result<LocalMessage>::failure(result.error()));
            return;
        }
        callback(Result<LocalMessage>::success(messageFromJson(result.value().object(), MessageDirection::Sent)));
    });
}

void HttpMessageGateway::listReceived(const QString& accessToken, GatewayCallback<MessageList> callback) {
    m_client.get(messagePath("/received?limit=50&offset=0"), accessToken, [this, callback = std::move(callback)](Result<QJsonDocument> result) mutable {
        if (result.failed()) {
            callback(Result<MessageList>::failure(result.error()));
            return;
        }
        callback(Result<MessageList>::success(messageListFromJson(result.value().array(), MessageDirection::Received)));
    });
}

void HttpMessageGateway::listSent(const QString& accessToken, GatewayCallback<MessageList> callback) {
    m_client.get(messagePath("/sent?limit=50&offset=0"), accessToken, [this, callback = std::move(callback)](Result<QJsonDocument> result) mutable {
        if (result.failed()) {
            callback(Result<MessageList>::failure(result.error()));
            return;
        }
        callback(Result<MessageList>::success(messageListFromJson(result.value().array(), MessageDirection::Sent)));
    });
}

void HttpMessageGateway::getMessage(const QString& accessToken, const QString& messageId, GatewayCallback<LocalMessage> callback) {
    m_client.get(messagePath(QString("/%1").arg(messageId)), accessToken, [this, callback = std::move(callback)](Result<QJsonDocument> result) mutable {
        if (result.failed()) {
            callback(Result<LocalMessage>::failure(result.error()));
            return;
        }
        callback(Result<LocalMessage>::success(messageFromJson(result.value().object(), MessageDirection::Received)));
    });
}

void HttpMessageGateway::forwardMessage(const QString& accessToken, const QString& originalMessageId, const LocalMessage& draft, std::optional<int> consumedPreKeyId, GatewayCallback<LocalMessage> callback) {
    m_client.post(messagePath(QString("/%1/forward").arg(originalMessageId)), accessToken, sendBodyFor(draft, consumedPreKeyId), [this, callback = std::move(callback)](Result<QJsonDocument> result) mutable {
        if (result.failed()) {
            callback(Result<LocalMessage>::failure(result.error()));
            return;
        }
        callback(Result<LocalMessage>::success(messageFromJson(result.value().object(), MessageDirection::Sent)));
    });
}

void HttpMessageGateway::revokeMessage(const QString& accessToken, const QString& messageId, GatewayCallback<LocalMessage> callback) {
    m_client.post(messagePath(QString("/%1/revoke").arg(messageId)), accessToken, {}, [this, callback = std::move(callback)](Result<QJsonDocument> result) mutable {
        if (result.failed()) {
            callback(Result<LocalMessage>::failure(result.error()));
            return;
        }
        callback(Result<LocalMessage>::success(messageFromJson(result.value().object(), MessageDirection::Sent)));
    });
}

void HttpMessageGateway::deleteMessage(const QString& accessToken, const QString& messageId, GatewayCallback<bool> callback) {
    m_client.deleteResource(messagePath(QString("/%1").arg(messageId)), accessToken, [callback = std::move(callback)](Result<QJsonDocument> result) mutable {
        if (result.failed()) {
            callback(Result<bool>::failure(result.error()));
            return;
        }
        callback(Result<bool>::success(true));
    });
}

QJsonObject HttpMessageGateway::sendBodyFor(const LocalMessage& draft, std::optional<int> consumedPreKeyId) const {
    QJsonObject body{
        {"sender_device_id", draft.senderDeviceId},
        {"recipient_user_id", draft.recipientUserId},
        {"recipient_device_id", draft.recipientDeviceId},
        {"wire_payload_json", draft.wirePayloadJson}
    };
    if (consumedPreKeyId.has_value()) {
        body.insert("consumed_one_time_prekey_id", *consumedPreKeyId);
    }
    return body;
}

LocalMessage HttpMessageGateway::messageFromJson(const QJsonObject& object, MessageDirection direction) const {
    return {
        object.value("id").toString(),
        object.value("sender_user_id").toString(),
        object.value("sender_device_id").toInt(),
        object.value("recipient_user_id").toString(),
        object.value("recipient_device_id").toInt(),
        object.value("wire_payload_json").toString(),
        object.value("consumed_one_time_prekey_id").isDouble()
            ? std::optional<int>(object.value("consumed_one_time_prekey_id").toInt())
            : std::nullopt,
        QDateTime::fromString(object.value("created_at").toString(), Qt::ISODateWithMs),
        object.value("access_revoked_at").toString(),
        object.value("sender_deleted_at").toString(),
        object.value("recipient_deleted_at").toString(),
        object.value("deleted_at").toString(),
        direction
    };
}

MessageList HttpMessageGateway::messageListFromJson(const QJsonArray& array, MessageDirection direction) const {
    MessageList messages;
    for (const auto value : array) {
        messages.push_back(messageFromJson(value.toObject(), direction));
    }
    return messages;
}
