#include "domain/Models.h"

#include "support/ClientConstants.h"

#include <unordered_map>

namespace {
using CommandLookup = std::unordered_map<std::string, CommandType>;

std::string commandKey(const QString& name) {
    return name.trimmed().toLower().toStdString();
}

const CommandLookup& commandLookup() {
    static const CommandLookup commands{
        {CommandNames::Help.toStdString(), CommandType::Help},
        {CommandNames::Register.toStdString(), CommandType::Register},
        {CommandNames::Login.toStdString(), CommandType::Login},
        {CommandNames::Logout.toStdString(), CommandType::Logout},
        {CommandNames::Whoami.toStdString(), CommandType::Whoami},
        {CommandNames::Status.toStdString(), CommandType::Status},
        {CommandNames::Conversations.toStdString(), CommandType::Conversations},
        {CommandNames::Inbox.toStdString(), CommandType::Inbox},
        {CommandNames::Sent.toStdString(), CommandType::Sent},
        {CommandNames::Msg.toStdString(), CommandType::Msg},
        {CommandNames::Send.toStdString(), CommandType::Send},
        {CommandNames::Read.toStdString(), CommandType::Read},
        {CommandNames::Forward.toStdString(), CommandType::Forward},
        {CommandNames::Revoke.toStdString(), CommandType::Revoke},
        {CommandNames::Delete.toStdString(), CommandType::DeleteMessage},
        {CommandNames::Download.toStdString(), CommandType::Download},
        {CommandNames::Trust.toStdString(), CommandType::Trust},
        {CommandNames::Verify.toStdString(), CommandType::Verify},
        {CommandNames::Sync.toStdString(), CommandType::Sync},
        {CommandNames::Cancel.toStdString(), CommandType::Cancel},
        {CommandNames::Exit.toStdString(), CommandType::Exit},
    };
    return commands;
}
}

QString errorCodeToString(ErrorCode code) {
    switch (code) {
    case ErrorCode::InvalidCommand:
        return "invalid-command";
    case ErrorCode::InvalidConfiguration:
        return "invalid-configuration";
    case ErrorCode::AuthRequired:
        return "auth-required";
    case ErrorCode::NetworkError:
        return "network-error";
    case ErrorCode::TlsError:
        return "tls-error";
    case ErrorCode::HttpError:
        return "http-error";
    case ErrorCode::CryptoError:
        return "crypto-error";
    case ErrorCode::TrustError:
        return "trust-error";
    case ErrorCode::StorageError:
        return "storage-error";
    case ErrorCode::NotFound:
        return "not-found";
    case ErrorCode::OperationFailed:
        return "operation-failed";
    }
    return "unknown";
}

QString commandTypeName(CommandType type) {
    for (const auto& [name, commandType] : commandLookup()) {
        if (commandType == type) {
            return QString::fromStdString(name);
        }
    }
    return "unknown";
}

std::optional<CommandType> commandTypeFromName(const QString& name) {
    const auto found = commandLookup().find(commandKey(name));
    if (found != commandLookup().cend()) {
        return found->second;
    }
    return std::nullopt;
}

QString clientModeToString(ClientMode mode) {
    if (mode == ClientMode::Real) {
        return AppText::RealMode;
    }
    return AppText::MockMode;
}

void registerClientMetaTypes() {
    qRegisterMetaType<ClientError>("ClientError");
    qRegisterMetaType<StartupConfig>("StartupConfig");
    qRegisterMetaType<SlashCommand>("SlashCommand");
    qRegisterMetaType<UserProfile>("UserProfile");
    qRegisterMetaType<UserAddress>("UserAddress");
    qRegisterMetaType<TokenSet>("TokenSet");
    qRegisterMetaType<AuthSession>("AuthSession");
    qRegisterMetaType<DeviceKeyMaterial>("DeviceKeyMaterial");
    qRegisterMetaType<OneTimePreKey>("OneTimePreKey");
    qRegisterMetaType<PreKeyBundle>("PreKeyBundle");
    qRegisterMetaType<TrustPin>("TrustPin");
    qRegisterMetaType<EncryptedPayload>("EncryptedPayload");
    qRegisterMetaType<LocalMessage>("LocalMessage");
    qRegisterMetaType<MessageList>("MessageList");
    qRegisterMetaType<ConversationSummary>("ConversationSummary");
    qRegisterMetaType<ConversationList>("ConversationList");
}
