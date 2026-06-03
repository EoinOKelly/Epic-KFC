#pragma once

#include <QString>

namespace AppText {
inline const QString ApplicationName = "EpicKfcClient";
inline const QString OrganizationName = "CS4455";
inline const QString DefaultStateFile = "client-state.json";
inline const QString DefaultApiUrl = "https://kfc.theburkenator.com/api/v1";
inline const QString DefaultMode = "real";
inline const QString MockMode = "mock";
inline const QString RealMode = "real";
inline const QString ApiPrefix = "/api/v1";
inline const QString BearerPrefix = "Bearer ";
inline const QString JsonContentType = "application/json";
inline constexpr int HttpRequestTimeoutMilliseconds = 30000;
inline const QString ModeFlag = "--mode";
inline const QString DebugFlag = "--debug";
inline const QString DebugErrorsFlag = "--debug-errors";
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
inline const QString DebugRealModeConflict = "--debug starts mock mode and cannot be combined with --mode real.";
inline const QString DebugApiUrlConflict = "--debug starts mock mode and cannot be combined with --api-url.";
inline const QString TlsRequired = "Real mode requires HTTPS with certificate validation.";
inline const QString HttpRequestTimedOut = "Request timed out while contacting the backend.";
inline const QString OperationInProgress = "Operation still in progress. Please wait for it to finish.";
inline const QString StartupUsage =
    "Usage: client [--debug] [--debug-errors] [--mode mock|real] [--api-url https://host/api/v1] [--device-id 1] [--state-path path]";
inline const QString Prompt = "> ";
inline const QString ConversationPrompt = "[%1] > ";
inline const QString PasswordPrompt = "password> ";
inline const QString MessagePrompt = "message> ";
inline const QString Greeting = "Epic KFC secure messaging client. Type /help to begin.";
inline const QString MockStatus = "Mock mode is active. No backend is required. Device ID: %1";
inline const QString RealStatus = "Real mode is active. Backend API: %1. Device ID: %2";
inline const QString AuthRequired = "You must /login before using this command.";
inline const QString UsernameResolveUnavailable = "Username lookup failed. Check the username and login state.";
inline const QString EmptyUsername = "Username must not be empty.";
inline const QString NoComposition = "There is no active message composition.";
inline const QString EmptyMessage = "Cannot send an empty message.";
inline const QString RegisteringUser = "Registering user...";
inline const QString LoggingIn = "Logging in...";
inline const QString LoggingOut = "Logging out...";
inline const QString LoadingConversations = "Loading conversations...";
inline const QString LoadingUnreadInbox = "Loading unread inbox...";
inline const QString SyncingMessages = "Syncing messages...";
inline const QString LoadingSentMessages = "Loading sent messages...";
inline const QString LoadingConversation = "Loading conversation...";
inline const QString ForwardingMessage = "Forwarding message...";
inline const QString RevokingMessage = "Revoking message...";
inline const QString DeletingMessage = "Deleting message...";
inline const QString ExportingMessage = "Exporting message...";
inline const QString CheckingTrust = "Checking trust...";
inline const QString VerifyingMessage = "Verifying message...";
inline const QString SendingMessage = "Sending message...";
inline const QString AnchorUnavailable = "No blockchain anchor is available for %1 yet.";
inline const QString AnchorPending = "Blockchain anchor for %1 is %2 on %3. Verification will be available once it is confirmed.";
inline const QString AnchorFailed = "Blockchain anchor for %1 failed on %2. Fidelity cannot be verified yet.";
inline const QString AnchorVerified = "Blockchain anchor verified for %1 on %2. Status: %3.";
inline const QString AnchorVerifiedWithTransaction = "Blockchain anchor verified for %1 on %2. Status: %3. Transaction: %4";
inline const QString AnchorMismatch = "Blockchain anchor check failed for %1. Fidelity could not be verified.";
inline const QString NotLoggedIn = "Not logged in.";
inline const QString LoggedInAs = "Logged in as %1 (%2).";
inline const QString RegisteredUser = "Registered %1. Use /login to start a session.";
inline const QString SessionEnded = "Session ended.";
inline const QString ReturnedToMainMenu = "Returned to the main menu.";
inline const QString KeysUploaded = "Device keys uploaded for device %1.";
inline const QString NativeCryptoUnavailable = "Real mode requires OpenSSL-backed native crypto. Install OpenSSL 3 development libraries and rebuild the client.";
inline const QString CompositionStarted = "Composing message for %1. Type body lines, /send to submit, or /cancel.";
inline const QString CompositionCancelled = "Message composition cancelled.";
inline const QString DraftLength = "Draft length: %1 character(s).";
inline const QString MessageSent = "Message %1 sent.";
inline const QString MessageOpened = "Message %1:";
inline const QString MessageForwarded = "Message forwarded as %1.";
inline const QString MessageRevoked = "Message %1 revoked.";
inline const QString MessageDeleted = "Message %1 deleted.";
inline const QString MessageDownloaded = "Message %1 exported to %2.";
inline const QString TrustFirstUse = "Pinned first-use identity.";
inline const QString TrustAlreadyMatches = "Identity is already trusted.";
inline const QString TrustMismatch = "Trust mismatch. Sending is blocked.";
inline const QString EmptyConversationList = "No cached conversations found.";
inline const QString EmptyUnreadInbox = "No unread messages.";
inline const QString EmptyMessageList = "No messages found.";
inline const QString ConversationHeader = "Conversations:";
inline const QString UnreadInboxHeader = "Unread inbox:";
inline const QString ConversationLogHeader = "Conversation with %1 (%2), page %3/%4:";
inline const QString ConversationLogLine = "  [%1] %2 %3: %4";
inline const QString ConversationLogDecryptFailed = "  [%1] %2 %3: <could not decrypt: %4>";
inline const QString SentMessageCiphertextOnly = "<sent message encrypted for recipient>";
inline const QString SentMessageLocalCopyUnavailable = "This sent message was cached before local sender-copy encryption was available.";
inline const QString MessageHeader = "Messages:";
inline const QString ErrorPrefix = "Error [";
inline const QString ErrorSeparator = "]: ";
inline const QString InvalidCommandError = "That command could not be understood. Type /help to see available commands.";
inline const QString InvalidConfigurationError = "The client startup options are invalid.";
inline const QString AuthRequiredError = "Authentication failed or your session expired. Log in and try again.";
inline const QString NetworkError = "The backend could not be reached. Check the server status and try again.";
inline const QString TlsError = "The secure connection failed. Certificate validation or TLS setup needs attention.";
inline const QString HttpError = "The server could not complete that request. Please try again later.";
inline const QString CryptoError = "The message could not be processed securely.";
inline const QString TrustError = "The recipient is not trusted yet, or their trusted identity changed.";
inline const QString StorageError = "The local client state could not be read or written.";
inline const QString NotFoundError = "The requested item could not be found.";
inline const QString OperationFailedError = "The operation could not be completed.";
inline const QString DebugErrorHint = " Run with --debug-errors to show technical details.";
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
    "  /msg <username> [message]\n"
    "  /send [message]\n"
    "  /read <username> [page]\n"
    "  /forward <messageId> <username>\n"
    "  /revoke <messageId>\n"
    "  /delete <messageId>\n"
    "  /download <messageId> <path>\n"
    "  /trust <username>\n"
    "  /verify <messageId>\n"
    "  /sync\n"
    "  /cancel\n"
    "  /back\n"
    "  /exit";
}

namespace CommandText {
inline constexpr QChar SlashPrefix = '/';
inline constexpr QChar Quote = '"';
inline constexpr QChar Escape = '\\';
inline constexpr QChar Space = ' ';
inline const QString SubmitCommand = "/send";
inline const QString CancelCommand = "/cancel";
inline const QString BackCommand = "/back";
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
inline const QString PositivePage = "/%1 expects page to be a positive integer.";
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
inline const QString Msg = "msg";
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
inline const QString Back = "back";
inline const QString Exit = "exit";
}

namespace StorageKeys {
inline const QString RootVersion = "version";
inline const QString AccessToken = "accessToken";
inline const QString RefreshToken = "refreshToken";
inline const QString CurrentUser = "currentUser";
inline const QString DeviceKeys = "deviceKeys";
inline const QString OneTimePreKeys = "oneTimePreKeys";
inline const QString KnownUsers = "knownUsers";
inline const QString TrustPins = "trustPins";
inline const QString Messages = "messages";
inline const QString Sessions = "sessions";
inline const QString LastAccountId = "lastAccountId";
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
inline const QString ReadAt = "readAt";
inline const QString LocalSenderCopyWirePayloadJson = "localSenderCopyWirePayloadJson";
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
inline const QString WireFormat = "format";
inline const QString WireFormatValue = "libsignal-v1";
inline const QString WireType = "type";
inline const QString WireBodyB64 = "bodyB64";
inline const QString WireRegistrationId = "registrationId";
inline constexpr int WireWhisperMessageType = 1;
inline constexpr int WirePreKeyWhisperMessageType = 3;
inline constexpr qsizetype KeyBytes = 32;
inline constexpr qsizetype IvBytes = 12;
inline constexpr qsizetype AuthTagBytes = 16;
inline constexpr int DefaultPreKeyCount = 8;
inline constexpr int FirstPreKeyId = 1;
inline constexpr int SignedPreKeyId = 1;
inline constexpr int DefaultRegistrationIdMinimum = 10000;
inline constexpr int DefaultRegistrationIdRange = 90000;
}

namespace Paging {
inline constexpr int ConversationPageSize = 10;
}
