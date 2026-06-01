#include "services/Services.h"

#include "support/ClientConstants.h"

#include <QFile>
#include <QTextStream>

#include <algorithm>

namespace {
constexpr int ConflictStatusCode = 409;

bool isAlreadyUploadedPreKeyError(const ClientError& error) {
    const bool isHttpError = error.code == ErrorCode::HttpError;
    const bool isConflict = error.message.contains(QString::number(ConflictStatusCode));
    const bool mentionsPreKey = error.message.contains("prekey", Qt::CaseInsensitive)
        || error.message.contains("pre-key", Qt::CaseInsensitive);
    const bool mentionsExisting = error.message.contains("already", Qt::CaseInsensitive)
        || error.message.contains("exists", Qt::CaseInsensitive);
    return isHttpError && isConflict && mentionsPreKey && mentionsExisting;
}
}

SessionService::SessionService(EventBus& events, IAuthGateway& authGateway, JsonLocalStore& store, bool accountScopedState, QObject* parent)
    : QObject(parent)
    , m_events(events)
    , m_authGateway(authGateway)
    , m_store(store)
    , m_accountScopedState(accountScopedState) {
    const auto loaded = m_store.loadSession();
    if (loaded.succeeded() && loaded.value().has_value()) {
        m_session = *loaded.value();
    }
}

void SessionService::registerUser(const QString& username, const QString& email, const QString& password) {
    m_authGateway.registerUser(username, email, password, [this](Result<UserProfile> result) {
        if (result.failed()) {
            emit m_events.commandFailed(result.error());
            return;
        }
        emit m_events.statusMessage(QString(AppText::RegisteredUser).arg(result.value().username));
    });
}

void SessionService::login(const QString& usernameOrEmail, const QString& password) {
    m_authGateway.login(usernameOrEmail, password, [this, password](Result<AuthSession> result) {
        if (result.failed()) {
            emit m_events.commandFailed(result.error());
            return;
        }
        m_store.setSecretPassphrase(password);
        if (m_accountScopedState) {
            m_store.useAccountScopedPath(result.value().user.id);
        }
        const auto loadedLocalState = m_store.reload();
        if (loadedLocalState.failed()) {
            emit m_events.commandFailed(loadedLocalState.error());
            return;
        }

        m_session = result.value();
        const auto saved = m_store.saveSession(*m_session);
        if (saved.failed()) {
            emit m_events.commandFailed(saved.error());
            return;
        }
        emit m_events.sessionStarted(m_session->user);
    });
}

void SessionService::logout() {
    const QString refreshToken = m_session.has_value() ? m_session->tokens.refreshToken : QString();
    m_authGateway.logout(refreshToken, [this](Result<bool> result) {
        if (result.failed()) {
            emit m_events.commandFailed(result.error());
            return;
        }
        m_session.reset();
        const auto cleared = m_store.clearSession();
        if (cleared.failed()) {
            emit m_events.commandFailed(cleared.error());
            return;
        }
        m_store.clearSecretPassphrase();
        emit m_events.sessionEnded();
    });
}

bool SessionService::isLoggedIn() const {
    return m_session.has_value();
}

std::optional<AuthSession> SessionService::currentSession() const {
    return m_session;
}

QString SessionService::accessToken() const {
    if (!m_session.has_value()) {
        return {};
    }
    return m_session->tokens.accessToken;
}

QString SessionService::currentUserId() const {
    if (!m_session.has_value()) {
        return {};
    }
    return m_session->user.id;
}

void SessionService::updateTokens(const TokenSet& tokens) {
    if (!m_session.has_value()) {
        return;
    }
    m_session->tokens = tokens;
    const auto saved = m_store.saveSession(*m_session);
    if (saved.failed()) {
        emit m_events.commandFailed(saved.error());
    }
}

KeyService::KeyService(EventBus& events, IKeyGateway& keyGateway, IUserDirectoryGateway& userDirectoryGateway, ICryptoProvider& cryptoProvider, JsonLocalStore& store, SessionService& sessionService, int deviceId, QObject* parent)
    : QObject(parent)
    , m_events(events)
    , m_keyGateway(keyGateway)
    , m_userDirectoryGateway(userDirectoryGateway)
    , m_cryptoProvider(cryptoProvider)
    , m_store(store)
    , m_sessionService(sessionService)
    , m_deviceId(deviceId) {
}

void KeyService::ensureDeviceKeysUploaded() {
    if (!m_sessionService.isLoggedIn()) {
        emit m_events.commandFailed({ErrorCode::AuthRequired, AppText::AuthRequired});
        return;
    }

    const auto loaded = m_store.loadDeviceKeys(m_deviceId);
    if (loaded.failed()) {
        emit m_events.commandFailed(loaded.error());
        return;
    }

    DeviceKeyMaterial existing;
    if (loaded.value().has_value()) {
        existing = *loaded.value();
    }

    const auto material = m_cryptoProvider.loadOrCreateDevice(existing, m_deviceId);
    if (material.failed()) {
        emit m_events.cryptoOperationFailed(material.error());
        return;
    }

    const auto savedDevice = m_store.saveDeviceKeys(material.value());
    if (savedDevice.failed()) {
        emit m_events.commandFailed(savedDevice.error());
        return;
    }
    m_keyGateway.upsertDeviceKeys(m_sessionService.accessToken(), material.value(), [this](Result<bool> result) {
        if (result.failed()) {
            emit m_events.commandFailed(result.error());
            return;
        }
        uploadOneTimePreKeys();
        emit m_events.deviceKeysReady(m_deviceId);
    });
}

void KeyService::uploadOneTimePreKeys() {
    auto existing = m_store.loadOneTimePreKeys(m_deviceId);
    if (existing.failed() || existing.value().empty()) {
        const auto created = m_cryptoProvider.createOneTimePreKeys(m_deviceId, CryptoText::DefaultPreKeyCount);
        if (created.failed()) {
            emit m_events.cryptoOperationFailed(created.error());
            return;
        }
        const auto savedPreKeys = m_store.saveOneTimePreKeys(created.value());
        if (savedPreKeys.failed()) {
            emit m_events.commandFailed(savedPreKeys.error());
            return;
        }
        existing = Result<std::vector<OneTimePreKey>>::success(created.value());
    }

    m_keyGateway.uploadOneTimePreKeys(m_sessionService.accessToken(), m_deviceId, existing.value(), [this](Result<bool> result) {
        if (result.failed()) {
            if (isAlreadyUploadedPreKeyError(result.error())) {
                return;
            }
            emit m_events.commandFailed(result.error());
        }
    });
}

void KeyService::trustUsername(const QString& username) {
    if (!m_sessionService.isLoggedIn()) {
        emit m_events.commandFailed({ErrorCode::AuthRequired, AppText::AuthRequired});
        return;
    }

    m_userDirectoryGateway.resolveUsername(m_sessionService.accessToken(), username, m_deviceId, [this](Result<UserAddress> addressResult) {
        if (addressResult.failed()) {
            emit m_events.commandFailed(addressResult.error());
            return;
        }
        const UserAddress address = addressResult.value();
        const auto savedUser = m_store.saveKnownUser(address);
        if (savedUser.failed()) {
            emit m_events.commandFailed(savedUser.error());
            return;
        }
        m_keyGateway.fetchPreKeyBundle(m_sessionService.accessToken(), address.userId, address.deviceId, [this, address](Result<PreKeyBundle> result) {
            if (result.failed()) {
                emit m_events.commandFailed(result.error());
                return;
            }
            const auto verified = m_cryptoProvider.verifySignedPreKey(result.value());
            if (verified.failed()) {
                emit m_events.cryptoOperationFailed(verified.error());
                return;
            }

            const auto existing = m_store.trustPin(address.userId, address.deviceId);
            if (existing.failed()) {
                emit m_events.commandFailed(existing.error());
                return;
            }
            if (!existing.value().has_value()) {
                TrustPin pin{address.userId, address.deviceId, result.value().identityKey, QDateTime::currentDateTimeUtc()};
                const auto saved = m_store.saveTrustPin(pin);
                if (saved.failed()) {
                    emit m_events.commandFailed(saved.error());
                    return;
                }
                m_lastTrustedBundle = result.value();
                emit m_events.trustPinCreated(pin);
                return;
            }
            if (existing.value()->identityKey != result.value().identityKey) {
                emit m_events.trustPinMismatch(address.userId, address.deviceId);
                return;
            }
            m_lastTrustedBundle = result.value();
            emit m_events.trustPinMatched(address.userId, address.deviceId);
        });
    });
}

Result<DeviceKeyMaterial> KeyService::currentDevice() {
    const auto loaded = m_store.loadDeviceKeys(m_deviceId);
    if (loaded.failed()) {
        return Result<DeviceKeyMaterial>::failure(loaded.error());
    }
    if (!loaded.value().has_value()) {
        return Result<DeviceKeyMaterial>::failure({ErrorCode::CryptoError, "Device keys are not available. Login first."});
    }
    return Result<DeviceKeyMaterial>::success(*loaded.value());
}

Result<std::optional<TrustPin>> KeyService::trustPin(const QString& userId, int deviceId) const {
    return m_store.trustPin(userId, deviceId);
}

Result<PreKeyBundle> KeyService::cachedBundle(const QString& userId, int deviceId) const {
    if (m_lastTrustedBundle.has_value()
        && m_lastTrustedBundle->userId == userId
        && m_lastTrustedBundle->deviceId == deviceId) {
        return Result<PreKeyBundle>::success(*m_lastTrustedBundle);
    }
    return Result<PreKeyBundle>::failure({ErrorCode::TrustError, "Run /trust for this username before sending."});
}

MessageService::MessageService(EventBus& events, IMessageGateway& messageGateway, IUserDirectoryGateway& userDirectoryGateway, ICryptoProvider& cryptoProvider, JsonLocalStore& store, SessionService& sessionService, KeyService& keyService, int deviceId, QObject* parent)
    : QObject(parent)
    , m_events(events)
    , m_messageGateway(messageGateway)
    , m_userDirectoryGateway(userDirectoryGateway)
    , m_cryptoProvider(cryptoProvider)
    , m_store(store)
    , m_sessionService(sessionService)
    , m_keyService(keyService)
    , m_deviceId(deviceId) {
}

void MessageService::listReceived() {
    if (!requireSession()) {
        return;
    }
    m_messageGateway.listReceived(m_sessionService.accessToken(), [this](Result<MessageList> result) {
        if (result.failed()) {
            emit m_events.commandFailed(result.error());
            return;
        }
        saveAndEmitList(result.value());
    });
}

void MessageService::listSent() {
    if (!requireSession()) {
        return;
    }
    m_messageGateway.listSent(m_sessionService.accessToken(), [this](Result<MessageList> result) {
        if (result.failed()) {
            emit m_events.commandFailed(result.error());
            return;
        }
        saveAndEmitList(result.value());
    });
}

void MessageService::listConversations() {
    if (!requireSession()) {
        return;
    }
    m_messageGateway.listReceived(m_sessionService.accessToken(), [this](Result<MessageList> receivedResult) {
        if (receivedResult.failed()) {
            emit m_events.commandFailed(receivedResult.error());
            return;
        }
        saveMessages(receivedResult.value());
        m_messageGateway.listSent(m_sessionService.accessToken(), [this](Result<MessageList> sentResult) {
            if (sentResult.failed()) {
                emit m_events.commandFailed(sentResult.error());
                return;
            }
            saveMessages(sentResult.value());
            const auto conversations = m_store.conversationsFor(m_sessionService.currentUserId());
            if (conversations.failed()) {
                emit m_events.commandFailed(conversations.error());
                return;
            }
            emit m_events.conversationListUpdated(conversations.value());
        });
    });
}

void MessageService::listUnreadSenders() {
    if (!requireSession()) {
        return;
    }
    m_messageGateway.listReceived(m_sessionService.accessToken(), [this](Result<MessageList> result) {
        if (result.failed()) {
            emit m_events.commandFailed(result.error());
            return;
        }
        saveMessages(result.value());
        const auto unread = m_store.unreadConversationsFor(m_sessionService.currentUserId());
        if (unread.failed()) {
            emit m_events.commandFailed(unread.error());
            return;
        }
        emit m_events.unreadInboxUpdated(unread.value());
    });
}

void MessageService::send(const QString& recipientUsername, const QString& plaintext) {
    if (!requireSession()) {
        return;
    }
    m_userDirectoryGateway.resolveUsername(m_sessionService.accessToken(), recipientUsername, m_deviceId, [this, plaintext](Result<UserAddress> result) {
        if (result.failed()) {
            emit m_events.commandFailed(result.error());
            return;
        }
        const auto savedUser = m_store.saveKnownUser(result.value());
        if (savedUser.failed()) {
            emit m_events.commandFailed(savedUser.error());
            return;
        }
        sendToAddress(result.value(), plaintext);
    });
}

void MessageService::sendToAddress(const UserAddress& recipientAddress, const QString& plaintext) {
    const auto device = m_keyService.currentDevice();
    const auto bundle = m_keyService.cachedBundle(recipientAddress.userId, recipientAddress.deviceId);
    if (device.failed()) {
        emit m_events.commandFailed(device.error());
        return;
    }
    if (bundle.failed()) {
        emit m_events.commandFailed(bundle.error());
        return;
    }

    const auto encrypted = m_cryptoProvider.encrypt(m_sessionService.currentUserId(), device.value(), bundle.value(), plaintext);
    if (encrypted.failed()) {
        emit m_events.cryptoOperationFailed(encrypted.error());
        return;
    }

    const LocalMessage draft = draftFor(recipientAddress.userId, recipientAddress.deviceId, encrypted.value().wirePayloadJson);
    m_messageGateway.sendMessage(m_sessionService.accessToken(), draft, encrypted.value().consumedOneTimePreKeyId, [this, plaintext](Result<LocalMessage> result) {
        if (result.failed()) {
            emit m_events.commandFailed(result.error());
            return;
        }
        LocalMessage savedMessage = result.value();
        savedMessage.localPlaintext = plaintext;
        const auto saved = m_store.saveMessage(savedMessage);
        if (saved.failed()) {
            emit m_events.commandFailed(saved.error());
            return;
        }
        emit m_events.messageSent(savedMessage);
    });
}

void MessageService::readConversation(const QString& username, int page) {
    if (!requireSession()) {
        return;
    }

    m_userDirectoryGateway.resolveUsername(m_sessionService.accessToken(), username, m_deviceId, [this, username, page](Result<UserAddress> addressResult) {
        if (addressResult.failed()) {
            emit m_events.commandFailed(addressResult.error());
            return;
        }
        const UserAddress address = addressResult.value();
        const auto savedUser = m_store.saveKnownUser(address);
        if (savedUser.failed()) {
            emit m_events.commandFailed(savedUser.error());
            return;
        }
        m_messageGateway.listReceived(m_sessionService.accessToken(), [this, address, username, page](Result<MessageList> receivedResult) {
            if (receivedResult.failed()) {
                emit m_events.commandFailed(receivedResult.error());
                return;
            }
            saveMessages(receivedResult.value());
            m_messageGateway.listSent(m_sessionService.accessToken(), [this, address, username, page](Result<MessageList> sentResult) {
                if (sentResult.failed()) {
                    emit m_events.commandFailed(sentResult.error());
                    return;
                }
                saveMessages(sentResult.value());
                openConversationFromCache(address, username, page);
            });
        });
    });
}

void MessageService::forward(const QString& messageId, const QString& recipientUsername) {
    if (!requireSession()) {
        return;
    }
    m_userDirectoryGateway.resolveUsername(m_sessionService.accessToken(), recipientUsername, m_deviceId, [this, messageId](Result<UserAddress> result) {
        if (result.failed()) {
            emit m_events.commandFailed(result.error());
            return;
        }
        const auto savedUser = m_store.saveKnownUser(result.value());
        if (savedUser.failed()) {
            emit m_events.commandFailed(savedUser.error());
            return;
        }
        forwardToAddress(messageId, result.value());
    });
}

void MessageService::forwardToAddress(const QString& messageId, const UserAddress& recipientAddress) {
    const auto found = m_store.findMessage(messageId);
    if (found.failed() || !found.value().has_value()) {
        emit m_events.commandFailed({ErrorCode::NotFound, "Message must be cached before forwarding. Use /read first."});
        return;
    }
    const auto device = m_keyService.currentDevice();
    if (device.failed()) {
        emit m_events.commandFailed(device.error());
        return;
    }
    const auto plaintext = m_cryptoProvider.decrypt(m_sessionService.currentUserId(), device.value(), *found.value(), oneTimePreKeyFor(*found.value()));
    if (plaintext.failed()) {
        emit m_events.cryptoOperationFailed(plaintext.error());
        return;
    }
    const auto bundle = m_keyService.cachedBundle(recipientAddress.userId, recipientAddress.deviceId);
    if (bundle.failed()) {
        emit m_events.commandFailed(bundle.error());
        return;
    }
    const auto encrypted = m_cryptoProvider.encrypt(m_sessionService.currentUserId(), device.value(), bundle.value(), plaintext.value());
    if (encrypted.failed()) {
        emit m_events.cryptoOperationFailed(encrypted.error());
        return;
    }
    const LocalMessage draft = draftFor(recipientAddress.userId, recipientAddress.deviceId, encrypted.value().wirePayloadJson);
    m_messageGateway.forwardMessage(m_sessionService.accessToken(), messageId, draft, encrypted.value().consumedOneTimePreKeyId, [this, plaintext](Result<LocalMessage> result) {
        if (result.failed()) {
            emit m_events.commandFailed(result.error());
            return;
        }
        LocalMessage savedMessage = result.value();
        savedMessage.localPlaintext = plaintext.value();
        const auto saved = m_store.saveMessage(savedMessage);
        if (saved.failed()) {
            emit m_events.commandFailed(saved.error());
            return;
        }
        emit m_events.messageForwarded(savedMessage);
    });
}

void MessageService::revoke(const QString& messageId) {
    m_messageGateway.revokeMessage(m_sessionService.accessToken(), messageId, [this, messageId](Result<LocalMessage> result) {
        if (result.failed()) {
            emit m_events.commandFailed(result.error());
            return;
        }
        const auto saved = m_store.saveMessage(result.value());
        if (saved.failed()) {
            emit m_events.commandFailed(saved.error());
            return;
        }
        emit m_events.messageRevoked(messageId);
    });
}

void MessageService::deleteMessage(const QString& messageId) {
    m_messageGateway.deleteMessage(m_sessionService.accessToken(), messageId, [this, messageId](Result<bool> result) {
        if (result.failed()) {
            emit m_events.commandFailed(result.error());
            return;
        }
        emit m_events.messageDeleted(messageId);
    });
}

void MessageService::download(const QString& messageId, const QString& path) {
    const auto found = m_store.findMessage(messageId);
    if (found.failed() || !found.value().has_value()) {
        emit m_events.commandFailed({ErrorCode::NotFound, "Message must be cached before download. Use /read first."});
        return;
    }
    const auto device = m_keyService.currentDevice();
    if (device.failed()) {
        emit m_events.commandFailed(device.error());
        return;
    }
    const auto plaintext = m_cryptoProvider.decrypt(m_sessionService.currentUserId(), device.value(), *found.value(), oneTimePreKeyFor(*found.value()));
    if (plaintext.failed()) {
        emit m_events.cryptoOperationFailed(plaintext.error());
        return;
    }
    QFile file(path);
    if (!file.open(QIODevice::WriteOnly | QIODevice::Truncate | QIODevice::Text)) {
        emit m_events.commandFailed({ErrorCode::StorageError, QString("Could not write %1.").arg(path)});
        return;
    }
    QTextStream output(&file);
    output << plaintext.value() << '\n';
    emit m_events.messageDownloaded(messageId, path);
}

void MessageService::verify(const QString& messageId) {
    emit m_events.fidelityStatusUpdated(messageId, QString(AppText::AnchorUnavailable).arg(messageId));
}

bool MessageService::requireSession() {
    if (m_sessionService.isLoggedIn()) {
        return true;
    }
    emit m_events.commandFailed({ErrorCode::AuthRequired, AppText::AuthRequired});
    return false;
}

std::optional<OneTimePreKey> MessageService::oneTimePreKeyFor(const LocalMessage& message) const {
    if (!message.consumedOneTimePreKeyId.has_value()) {
        return std::nullopt;
    }

    const auto loaded = m_store.loadOneTimePreKeys(m_deviceId);
    if (loaded.failed()) {
        return std::nullopt;
    }

    const int preKeyId = *message.consumedOneTimePreKeyId;
    const auto it = std::find_if(loaded.value().cbegin(), loaded.value().cend(), [preKeyId](const OneTimePreKey& preKey) {
        return preKey.preKeyId == preKeyId;
    });
    if (it == loaded.value().cend()) {
        return std::nullopt;
    }
    return *it;
}

void MessageService::saveAndEmitList(const MessageList& messages) {
    saveMessages(messages);
    emit m_events.messageListUpdated(messages);
}

void MessageService::saveMessages(const MessageList& messages) {
    for (const auto& message : messages) {
        const auto saved = m_store.saveMessage(message);
        if (saved.failed()) {
            emit m_events.commandFailed(saved.error());
            return;
        }
    }
}

void MessageService::openConversationFromCache(const UserAddress& address, const QString& username, int page) {
    const auto messages = m_store.messagesWithPeer(m_sessionService.currentUserId(), address.userId);
    if (messages.failed()) {
        emit m_events.commandFailed(messages.error());
        return;
    }
    if (messages.value().empty()) {
        emit m_events.commandFailed({ErrorCode::NotFound, QString("No cached conversation with %1.").arg(username)});
        return;
    }

    const int pageSize = Paging::ConversationPageSize;
    const int pageCount = static_cast<int>((messages.value().size() + pageSize - 1) / pageSize);
    const int safePage = std::clamp(page, 1, pageCount);
    const int start = (safePage - 1) * pageSize;
    const int end = std::min(start + pageSize, static_cast<int>(messages.value().size()));
    const auto device = m_keyService.currentDevice();
    if (device.failed()) {
        emit m_events.commandFailed(device.error());
        return;
    }

    ConversationLog entries;
    for (int index = start; index < end; ++index) {
        const LocalMessage& message = messages.value().at(index);
        ConversationLogEntry entry{message, {}, std::nullopt};
        const bool sentByCurrentUser = message.senderUserId == m_sessionService.currentUserId();
        if (sentByCurrentUser) {
            entry.plaintext = message.localPlaintext.isEmpty() ? AppText::SentMessageCiphertextOnly : message.localPlaintext;
            entries.push_back(entry);
            continue;
        }

        const auto plaintext = m_cryptoProvider.decrypt(m_sessionService.currentUserId(), device.value(), message, oneTimePreKeyFor(message));
        if (plaintext.succeeded()) {
            entry.plaintext = plaintext.value();
        } else {
            entry.decryptError = plaintext.error();
        }
        entries.push_back(entry);
    }

    const auto markedRead = m_store.markConversationRead(m_sessionService.currentUserId(), address.userId);
    if (markedRead.failed()) {
        emit m_events.commandFailed(markedRead.error());
        return;
    }
    emit m_events.conversationLogOpened(username, address.userId, entries, safePage, pageCount);
}

LocalMessage MessageService::draftFor(const QString& recipientUserId, int recipientDeviceId, const QString& wirePayloadJson) const {
    return {
        {},
        m_sessionService.currentUserId(),
        m_deviceId,
        recipientUserId,
        recipientDeviceId,
        wirePayloadJson,
        std::nullopt,
        {},
        {},
        {},
        {},
        {},
        {},
        {},
        MessageDirection::Sent
    };
}
