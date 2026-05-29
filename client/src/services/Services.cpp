#include "services/Services.h"

#include "support/ClientConstants.h"

#include <QFile>
#include <QTextStream>

#include <algorithm>

SessionService::SessionService(EventBus& events, IAuthGateway& authGateway, JsonLocalStore& store, QObject* parent)
    : QObject(parent)
    , m_events(events)
    , m_authGateway(authGateway)
    , m_store(store) {
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

KeyService::KeyService(EventBus& events, IKeyGateway& keyGateway, ICryptoProvider& cryptoProvider, JsonLocalStore& store, SessionService& sessionService, int deviceId, QObject* parent)
    : QObject(parent)
    , m_events(events)
    , m_keyGateway(keyGateway)
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
    if (existing.failed() || existing.value().isEmpty()) {
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
        existing = Result<QList<OneTimePreKey>>::success(created.value());
    }

    m_keyGateway.uploadOneTimePreKeys(m_sessionService.accessToken(), m_deviceId, existing.value(), [this](Result<bool> result) {
        if (result.failed()) {
            emit m_events.commandFailed(result.error());
        }
    });
}

void KeyService::trustUser(const QString& userId, int deviceId) {
    if (!m_sessionService.isLoggedIn()) {
        emit m_events.commandFailed({ErrorCode::AuthRequired, AppText::AuthRequired});
        return;
    }

    m_keyGateway.fetchPreKeyBundle(m_sessionService.accessToken(), userId, deviceId, [this, userId, deviceId](Result<PreKeyBundle> result) {
        if (result.failed()) {
            emit m_events.commandFailed(result.error());
            return;
        }
        const auto verified = m_cryptoProvider.verifySignedPreKey(result.value());
        if (verified.failed()) {
            emit m_events.cryptoOperationFailed(verified.error());
            return;
        }

        const auto existing = m_store.trustPin(userId, deviceId);
        if (existing.failed()) {
            emit m_events.commandFailed(existing.error());
            return;
        }
        if (!existing.value().has_value()) {
            TrustPin pin{userId, deviceId, result.value().identityKey, QDateTime::currentDateTimeUtc()};
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
            emit m_events.trustPinMismatch(userId, deviceId);
            return;
        }
        m_lastTrustedBundle = result.value();
        emit m_events.trustPinMatched(userId, deviceId);
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
    return Result<PreKeyBundle>::failure({ErrorCode::TrustError, "Run /trust for this user/device before sending."});
}

MessageService::MessageService(EventBus& events, IMessageGateway& messageGateway, ICryptoProvider& cryptoProvider, JsonLocalStore& store, SessionService& sessionService, KeyService& keyService, int deviceId, QObject* parent)
    : QObject(parent)
    , m_events(events)
    , m_messageGateway(messageGateway)
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
    const auto conversations = m_store.conversationsFor(m_sessionService.currentUserId());
    if (conversations.failed()) {
        emit m_events.commandFailed(conversations.error());
        return;
    }
    emit m_events.conversationListUpdated(conversations.value());
}

void MessageService::send(const QString& recipientUserId, int recipientDeviceId, const QString& plaintext) {
    if (!requireSession()) {
        return;
    }
    const auto device = m_keyService.currentDevice();
    const auto bundle = m_keyService.cachedBundle(recipientUserId, recipientDeviceId);
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

    const LocalMessage draft = draftFor(recipientUserId, recipientDeviceId, encrypted.value().wirePayloadJson);
    m_messageGateway.sendMessage(m_sessionService.accessToken(), draft, encrypted.value().consumedOneTimePreKeyId, [this](Result<LocalMessage> result) {
        if (result.failed()) {
            emit m_events.commandFailed(result.error());
            return;
        }
        const auto saved = m_store.saveMessage(result.value());
        if (saved.failed()) {
            emit m_events.commandFailed(saved.error());
            return;
        }
        emit m_events.messageSent(result.value());
    });
}

void MessageService::read(const QString& messageId) {
    if (!requireSession()) {
        return;
    }

    const auto found = m_store.findMessage(messageId);
    if (found.succeeded() && found.value().has_value()) {
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
        emit m_events.messageOpened(*found.value(), plaintext.value());
        return;
    }

    m_messageGateway.getMessage(m_sessionService.accessToken(), messageId, [this](Result<LocalMessage> result) {
        if (result.failed()) {
            emit m_events.commandFailed(result.error());
            return;
        }
        const auto saved = m_store.saveMessage(result.value());
        if (saved.failed()) {
            emit m_events.commandFailed(saved.error());
            return;
        }
        read(result.value().id);
    });
}

void MessageService::forward(const QString& messageId, const QString& recipientUserId, int recipientDeviceId) {
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
    const auto bundle = m_keyService.cachedBundle(recipientUserId, recipientDeviceId);
    if (bundle.failed()) {
        emit m_events.commandFailed(bundle.error());
        return;
    }
    const auto encrypted = m_cryptoProvider.encrypt(m_sessionService.currentUserId(), device.value(), bundle.value(), plaintext.value());
    if (encrypted.failed()) {
        emit m_events.cryptoOperationFailed(encrypted.error());
        return;
    }
    const LocalMessage draft = draftFor(recipientUserId, recipientDeviceId, encrypted.value().wirePayloadJson);
    m_messageGateway.forwardMessage(m_sessionService.accessToken(), messageId, draft, encrypted.value().consumedOneTimePreKeyId, [this](Result<LocalMessage> result) {
        if (result.failed()) {
            emit m_events.commandFailed(result.error());
            return;
        }
        const auto saved = m_store.saveMessage(result.value());
        if (saved.failed()) {
            emit m_events.commandFailed(saved.error());
            return;
        }
        emit m_events.messageForwarded(result.value());
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
    for (const auto& message : messages) {
        const auto saved = m_store.saveMessage(message);
        if (saved.failed()) {
            emit m_events.commandFailed(saved.error());
            return;
        }
    }
    emit m_events.messageListUpdated(messages);
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
        MessageDirection::Sent
    };
}
