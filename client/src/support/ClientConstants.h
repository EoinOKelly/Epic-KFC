#pragma once

#include <QString>

namespace AppText {
inline const QString ApplicationName = "EpicKfcClient";
inline const QString OrganizationName = "CS4455";
inline const QString DefaultStateFile = "client-state.json";
inline const QString DefaultMode = "mock";
inline const QString MockMode = "mock";
inline const QString RealMode = "real";
inline const QString ApiPrefix = "/api/v1";
inline const QString BearerPrefix = "Bearer ";
inline const QString JsonContentType = "application/json";
inline const QString ModeFlag = "--mode";
inline const QString ApiUrlFlag = "--api-url";
inline const QString DeviceIdFlag = "--device-id";
inline const QString StatePathFlag = "--state-path";
inline const QString HelpFlag = "--help";
inline const QString HttpsScheme = "https";
inline const QString LocalhostHost = "localhost";
inline const QString LoopbackHost = "127.0.0.1";
inline const QString Ipv6LoopbackHost = "::1";
inline const QString MissingRealApiUrl = "Real mode requires --api-url <https://host/api/v1>.";
inline const QString InvalidMode = "Mode must be mock or real.";
inline const QString InvalidDeviceId = "Device id must be a positive integer.";
inline const QString TlsRequired = "Real mode requires HTTPS except for localhost development URLs.";
inline const QString StartupUsage =
    "Usage: client [--mode mock|real] [--api-url https://host/api/v1] [--device-id 1] [--state-path path]";
inline const QString Prompt = "> ";
inline const QString PasswordPrompt = "password> ";
inline const QString MessagePrompt = "message> ";
inline const QString Greeting = "Epic KFC secure messaging client. Type /help to begin.";
inline const QString MockStatus = "Mock mode is active. No backend is required.";
inline const QString RealStatus = "Real mode is active. Backend API: %1";
inline const QString AuthRequired = "You must /login before using this command.";
inline const QString NoComposition = "There is no active message composition.";
inline const QString EmptyMessage = "Cannot send an empty message.";
inline const QString AnchorUnavailable = "Anchor unavailable for %1 because the backend has no anchor route yet.";
inline const QString NotLoggedIn = "Not logged in.";
inline const QString LoggedInAs = "Logged in as %1 (%2).";
inline const QString RegisteredUser = "Registered %1. Use /login to start a session.";
inline const QString SessionEnded = "Session ended.";
inline const QString KeysUploaded = "Device keys uploaded for device %1.";
inline const QString NativeCryptoUnavailable = "Real mode requires OpenSSL-backed native crypto. Install OpenSSL 3 development libraries and rebuild the client.";
inline const QString CompositionStarted = "Composing message for %1 device %2. Type body lines, /send to submit, or /cancel.";
inline const QString CompositionCancelled = "Message composition cancelled.";
inline const QString DraftLength = "Draft length: %1 character(s).";
inline const QString MessageSent = "Message %1 sent to %2 device %3.";
inline const QString MessageOpened = "Message %1:";
inline const QString MessageForwarded = "Message forwarded as %1.";
inline const QString MessageRevoked = "Message %1 revoked.";
inline const QString MessageDeleted = "Message %1 deleted.";
inline const QString MessageDownloaded = "Message %1 exported to %2.";
inline const QString TrustFirstUse = "Pinned first-use identity for %1 device %2.";
inline const QString TrustAlreadyMatches = "Identity for %1 device %2 is already trusted.";
inline const QString TrustMismatch = "Trust mismatch for %1 device %2. Sending is blocked.";
inline const QString EmptyConversationList = "No cached conversations found.";
inline const QString EmptyMessageList = "No messages found.";
inline const QString ConversationHeader = "Conversations:";
inline const QString MessageHeader = "Messages:";
inline const QString ErrorPrefix = "Error [";
inline const QString ErrorSeparator = "]: ";
inline const QString Help =
    "Available slash commands:\n"
    "  /help\n"
    "  /register <username> <email>\n"
    "  /login <usernameOrEmail>\n"
    "  /logout\n"
    "  /whoami\n"
    "  /status\n"
    "  /conversations\n"
    "  /inbox\n"
    "  /sent\n"
    "  /send <recipientUserUuid> [deviceId]\n"
    "  /read <messageId>\n"
    "  /forward <messageId> <recipientUserUuid> [deviceId]\n"
    "  /revoke <messageId>\n"
    "  /delete <messageId>\n"
    "  /download <messageId> <path>\n"
    "  /trust <userUuid> [deviceId]\n"
    "  /verify <messageId>\n"
    "  /sync\n"
    "  /cancel\n"
    "  /exit";
}

namespace CommandText {
inline constexpr QChar SlashPrefix = '/';
inline constexpr QChar Quote = '"';
inline constexpr QChar Escape = '\\';
inline constexpr QChar Space = ' ';
inline const QString SubmitCommand = "/send";
inline const QString CancelCommand = "/cancel";
inline const QString HelpPrompt = "Type /help to see available commands.";
inline const QString EmptyIgnored = "Empty input is ignored. %1";
inline const QString MissingSlash = "Commands must start with /. %1";
inline const QString MissingName = "Command name is missing after /. %1";
inline const QString UnknownCommand = "Unknown command /%1. %2";
inline const QString UnclosedQuote = "Quoted argument is missing its closing quote.";
inline const QString ArgumentCount = "/%1 expects %2.";
inline const QString AtLeast = "at least %1 argument(s)";
inline const QString Exactly = "%1 argument(s)";
inline const QString PositiveDeviceId = "/%1 expects deviceId to be a positive integer.";
}

namespace CommandNames {
inline const QString Help = "help";
inline const QString Register = "register";
inline const QString Login = "login";
inline const QString Logout = "logout";
inline const QString Whoami = "whoami";
inline const QString Status = "status";
inline const QString Conversations = "conversations";
inline const QString Inbox = "inbox";
inline const QString Sent = "sent";
inline const QString Send = "send";
inline const QString Read = "read";
inline const QString Forward = "forward";
inline const QString Revoke = "revoke";
inline const QString Delete = "delete";
inline const QString Download = "download";
inline const QString Trust = "trust";
inline const QString Verify = "verify";
inline const QString Sync = "sync";
inline const QString Cancel = "cancel";
inline const QString Exit = "exit";
}

namespace StorageKeys {
inline const QString RootVersion = "version";
inline const QString AccessToken = "accessToken";
inline const QString RefreshToken = "refreshToken";
inline const QString CurrentUser = "currentUser";
inline const QString DeviceKeys = "deviceKeys";
inline const QString OneTimePreKeys = "oneTimePreKeys";
inline const QString TrustPins = "trustPins";
inline const QString Messages = "messages";
inline const QString Sessions = "sessions";
inline const QString Id = "id";
inline const QString UserId = "userId";
inline const QString Username = "username";
inline const QString Email = "email";
inline const QString DeviceId = "deviceId";
inline const QString RegistrationId = "registrationId";
inline const QString IdentityKey = "identityKey";
inline const QString IdentityPrivateKey = "identityPrivateKey";
inline const QString IdentitySigningKey = "identitySigningKey";
inline const QString IdentitySigningPrivateKey = "identitySigningPrivateKey";
inline const QString SignedPreKeyId = "signedPreKeyId";
inline const QString SignedPreKey = "signedPreKey";
inline const QString SignedPreKeyPrivate = "signedPreKeyPrivate";
inline const QString SignedPreKeySignature = "signedPreKeySignature";
inline const QString PreKeyId = "preKeyId";
inline const QString PreKeyPublic = "preKeyPublic";
inline const QString PreKeyPrivate = "preKeyPrivate";
inline const QString FirstSeenAt = "firstSeenAt";
inline const QString SenderUserId = "senderUserId";
inline const QString SenderDeviceId = "senderDeviceId";
inline const QString RecipientUserId = "recipientUserId";
inline const QString RecipientDeviceId = "recipientDeviceId";
inline const QString WirePayloadJson = "wirePayloadJson";
inline const QString ConsumedOneTimePreKeyId = "consumedOneTimePreKeyId";
inline const QString CreatedAt = "createdAt";
inline const QString AccessRevokedAt = "accessRevokedAt";
inline const QString SenderDeletedAt = "senderDeletedAt";
inline const QString RecipientDeletedAt = "recipientDeletedAt";
inline const QString DeletedAt = "deletedAt";
}

namespace CryptoText {
inline const QString Protocol = "qt-native-signal-compatible-v1";
inline const QString X3dhInfo = "epic-messaging/v1/signal-x3dh-sk";
inline const QString LocalStorageInfo = "epic-messaging/v1/local-storage-key";
inline const QString WireCounter = "counter";
inline const QString WirePreviousCounter = "previousCounter";
inline const QString WireCiphertext = "ciphertext";
inline const QString WireIv = "iv";
inline const QString WireAuthTag = "authTag";
inline const QString WireRatchetPublicKey = "ratchetPublicKey";
inline const QString WireX3dh = "x3dh";
inline const QString WireIdentityKey = "identityKey";
inline const QString WireEphemeralKey = "ephemeralKey";
inline constexpr qsizetype KeyBytes = 32;
inline constexpr qsizetype IvBytes = 12;
inline constexpr qsizetype AuthTagBytes = 16;
inline constexpr int DefaultPreKeyCount = 8;
inline constexpr int FirstPreKeyId = 1;
inline constexpr int SignedPreKeyId = 1;
inline constexpr int DefaultRegistrationIdMinimum = 10000;
inline constexpr int DefaultRegistrationIdRange = 90000;
}
