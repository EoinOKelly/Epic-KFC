#pragma once

#include <QDateTime>
#include <QList>
#include <QMetaType>
#include <QString>
#include <QStringList>

#include <optional>

enum class ErrorCode {
    InvalidCommand,
    InvalidConfiguration,
    AuthRequired,
    NetworkError,
    TlsError,
    HttpError,
    CryptoError,
    TrustError,
    StorageError,
    NotFound,
    OperationFailed
};

enum class CommandType {
    Help,
    Register,
    Login,
    Logout,
    Whoami,
    Status,
    Conversations,
    Inbox,
    Sent,
    Msg,
    Send,
    Read,
    Forward,
    Revoke,
    DeleteMessage,
    Download,
    Trust,
    Verify,
    Sync,
    Cancel,
    Exit
};

enum class ClientMode {
    Mock,
    Real
};

enum class MessageDirection {
    Sent,
    Received
};

inline constexpr int DefaultDeviceId = 1;

struct ClientError {
    ErrorCode code{ErrorCode::OperationFailed};
    QString message;
};

struct StartupConfig {
    ClientMode mode{ClientMode::Mock};
    QString apiUrl;
    int deviceId{DefaultDeviceId};
    QString statePath;
};

struct SlashCommand {
    CommandType type{CommandType::Help};
    QString name;
    QStringList arguments;
    QString originalLine;
};

struct UserProfile {
    QString id;
    QString username;
    QString email;
};

struct TokenSet {
    QString accessToken;
    QString refreshToken;
    QString tokenType;
    int expiresIn{0};
};

struct AuthSession {
    UserProfile user;
    TokenSet tokens;
};

struct UserAddress {
    QString userId;
    QString username;
    int deviceId{DefaultDeviceId};
};

struct DeviceKeyMaterial {
    int deviceId{DefaultDeviceId};
    int registrationId{0};
    QString identityKey;
    QString identityPrivateKey;
    QString identitySigningKey;
    QString identitySigningPrivateKey;
    int signedPreKeyId{1};
    QString signedPreKey;
    QString signedPreKeyPrivate;
    QString signedPreKeySignature;
};

struct OneTimePreKey {
    int deviceId{DefaultDeviceId};
    int preKeyId{0};
    QString publicKey;
    QString privateKey;
    bool uploaded{false};
};

struct PreKeyBundle {
    QString userId;
    int registrationId{0};
    int deviceId{DefaultDeviceId};
    QString identityKey;
    QString identitySigningKey;
    int signedPreKeyId{0};
    QString signedPreKey;
    QString signedPreKeySignature;
    std::optional<int> oneTimePreKeyId;
    QString oneTimePreKey;
};

struct TrustPin {
    QString userId;
    int deviceId{DefaultDeviceId};
    QString identityKey;
    QDateTime firstSeenAt;
};

struct EncryptedPayload {
    QString wirePayloadJson;
    std::optional<int> consumedOneTimePreKeyId;
};

struct LocalMessage {
    QString id;
    QString senderUserId;
    int senderDeviceId{DefaultDeviceId};
    QString recipientUserId;
    int recipientDeviceId{DefaultDeviceId};
    QString wirePayloadJson;
    std::optional<int> consumedOneTimePreKeyId;
    QDateTime createdAt;
    QString accessRevokedAt;
    QString senderDeletedAt;
    QString recipientDeletedAt;
    QString deletedAt;
    MessageDirection direction{MessageDirection::Received};
};

struct ConversationSummary {
    QString peerUserId;
    int peerDeviceId{DefaultDeviceId};
    int messageCount{0};
    QDateTime latestMessageAt;
};

using MessageList = QList<LocalMessage>;
using ConversationList = QList<ConversationSummary>;

QString errorCodeToString(ErrorCode code);
QString commandTypeName(CommandType type);
std::optional<CommandType> commandTypeFromName(const QString& name);
QString clientModeToString(ClientMode mode);
void registerClientMetaTypes();

Q_DECLARE_METATYPE(ClientError)
Q_DECLARE_METATYPE(StartupConfig)
Q_DECLARE_METATYPE(SlashCommand)
Q_DECLARE_METATYPE(UserProfile)
Q_DECLARE_METATYPE(UserAddress)
Q_DECLARE_METATYPE(TokenSet)
Q_DECLARE_METATYPE(AuthSession)
Q_DECLARE_METATYPE(DeviceKeyMaterial)
Q_DECLARE_METATYPE(OneTimePreKey)
Q_DECLARE_METATYPE(PreKeyBundle)
Q_DECLARE_METATYPE(TrustPin)
Q_DECLARE_METATYPE(EncryptedPayload)
Q_DECLARE_METATYPE(LocalMessage)
Q_DECLARE_METATYPE(MessageList)
Q_DECLARE_METATYPE(ConversationSummary)
Q_DECLARE_METATYPE(ConversationList)
