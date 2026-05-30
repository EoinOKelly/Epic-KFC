#include "domain/Models.h"

#include "support/ClientConstants.h"

#include <array>
#include <utility>

namespace {
using CommandEntry = std::pair<QString, CommandType>;

const std::array<CommandEntry, 21>& commandLookup() {
    static const std::array<CommandEntry, 21> commands{{
        {CommandNames::Help, CommandType::Help},
        {CommandNames::Register, CommandType::Register},
        {CommandNames::Login, CommandType::Login},
        {CommandNames::Logout, CommandType::Logout},
        {CommandNames::Whoami, CommandType::Whoami},
        {CommandNames::Status, CommandType::Status},
        {CommandNames::Conversations, CommandType::Conversations},
        {CommandNames::Inbox, CommandType::Inbox},
        {CommandNames::Sent, CommandType::Sent},
        {CommandNames::Msg, CommandType::Msg},
        {CommandNames::Send, CommandType::Send},
        {CommandNames::Read, CommandType::Read},
        {CommandNames::Forward, CommandType::Forward},
        {CommandNames::Revoke, CommandType::Revoke},
        {CommandNames::Delete, CommandType::DeleteMessage},
        {CommandNames::Download, CommandType::Download},
        {CommandNames::Trust, CommandType::Trust},
        {CommandNames::Verify, CommandType::Verify},
        {CommandNames::Sync, CommandType::Sync},
        {CommandNames::Cancel, CommandType::Cancel},
        {CommandNames::Exit, CommandType::Exit},
    }};
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
            return name;
        }
    }
    return "unknown";
}

std::optional<CommandType> commandTypeFromName(const QString& name) {
    const QString key = name.trimmed().toLower();
    for (const auto& [commandName, commandType] : commandLookup()) {
        if (commandName == key) {
            return commandType;
        }
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
