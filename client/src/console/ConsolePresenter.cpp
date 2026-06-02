#include "console/ConsolePresenter.h"

#include "support/ClientConstants.h"

ConsolePresenter::ConsolePresenter(EventBus& events, bool showRawErrors, QObject* parent)
    : QObject(parent)
    , m_output(stdout)
    , m_showRawErrors(showRawErrors) {
    connect(&events, &EventBus::operationStarted, this, [this](const QString& message) {
        printOperation(message);
    });
    connect(&events, &EventBus::statusMessage, this, [this](const QString& message) {
        printMessage(message);
    });
    connect(&events, &EventBus::commandFailed, this, [this](const ClientError& error) {
        printError(error);
    });
    connect(&events, &EventBus::backendUnavailable, this, [this](const ClientError& error) {
        printError(error);
    });
    connect(&events, &EventBus::cryptoOperationFailed, this, [this](const ClientError& error) {
        printError(error);
    });
    connect(&events, &EventBus::sessionStarted, this, [this](const UserProfile& user) {
        printMessage(QString(AppText::LoggedInAs).arg(user.username, user.id));
    });
    connect(&events, &EventBus::sessionEnded, this, [this]() {
        printMessage(AppText::SessionEnded);
    });
    connect(&events, &EventBus::deviceKeysReady, this, [this](int deviceId) {
        printMessage(QString(AppText::KeysUploaded).arg(deviceId));
    });
    connect(&events, &EventBus::trustPinCreated, this, [this](const TrustPin& pin) {
        Q_UNUSED(pin)
        printMessage(AppText::TrustFirstUse);
    });
    connect(&events, &EventBus::trustPinMatched, this, [this](const QString& userId, int deviceId) {
        Q_UNUSED(userId)
        Q_UNUSED(deviceId)
        printMessage(AppText::TrustAlreadyMatches);
    });
    connect(&events, &EventBus::trustPinMismatch, this, [this](const QString& userId, int deviceId) {
        Q_UNUSED(userId)
        Q_UNUSED(deviceId)
        printError({ErrorCode::TrustError, AppText::TrustMismatch});
    });
    connect(&events, &EventBus::conversationListUpdated, this, [this](const ConversationList& conversations) {
        if (conversations.empty()) {
            printMessage(AppText::EmptyConversationList);
            return;
        }
        m_output << AppText::ConversationHeader << '\n';
        for (const auto& conversation : conversations) {
            Q_UNUSED(conversation.peerDeviceId)
            const QString peerName = conversation.peerUsername.isEmpty() ? conversation.peerUserId : conversation.peerUsername;
            m_output << "  " << peerName << " | messages=" << conversation.messageCount
                     << " | unread=" << conversation.unreadCount << '\n';
        }
        printPrompt();
    });
    connect(&events, &EventBus::unreadInboxUpdated, this, [this](const ConversationList& conversations) {
        if (conversations.empty()) {
            printMessage(AppText::EmptyUnreadInbox);
            return;
        }
        m_output << AppText::UnreadInboxHeader << '\n';
        for (const auto& conversation : conversations) {
            Q_UNUSED(conversation.peerDeviceId)
            const QString peerName = conversation.peerUsername.isEmpty() ? conversation.peerUserId : conversation.peerUsername;
            m_output << "  " << peerName << " | unread=" << conversation.unreadCount << '\n';
        }
        printPrompt();
    });
    connect(&events, &EventBus::conversationLogOpened, this, [this](const QString& username, const QString& peerUserId, const ConversationLog& entries, int page, int pageCount) {
        m_output << QString(AppText::ConversationLogHeader).arg(username, peerUserId).arg(page).arg(pageCount) << '\n';
        for (const auto& entry : entries) {
            const QString direction = entry.message.direction == MessageDirection::Sent ? "->" : "<-";
            const QString timestamp = entry.message.createdAt.toString(Qt::ISODate);
            if (entry.decryptError.has_value()) {
                const QString decryptError = m_showRawErrors
                    ? entry.decryptError->message
                    : safeErrorMessage(*entry.decryptError);
                m_output << QString(AppText::ConversationLogDecryptFailed)
                                .arg(timestamp, direction, entry.message.id, decryptError)
                         << '\n';
                continue;
            }
            m_output << QString(AppText::ConversationLogLine)
                            .arg(timestamp, direction, entry.message.id, entry.plaintext)
                     << '\n';
        }
        printPrompt();
    });
    connect(&events, &EventBus::messageListUpdated, this, [this](const MessageList& messages) {
        if (messages.empty()) {
            printMessage(AppText::EmptyMessageList);
            return;
        }
        m_output << AppText::MessageHeader << '\n';
        for (const auto& message : messages) {
            m_output << "  " << message.id << " | from=" << message.senderUserId
                     << " | to=" << message.recipientUserId << " | " << message.createdAt.toString(Qt::ISODate) << '\n';
        }
        printPrompt();
    });
    connect(&events, &EventBus::messagePrepared, this, [this](const QString& recipientUserId, int deviceId, const QString& body) {
        Q_UNUSED(deviceId)
        if (body.isEmpty()) {
            printMessage(QString(AppText::CompositionStarted).arg(recipientUserId));
            return;
        }
        printMessage(QString(AppText::DraftLength).arg(body.size()));
    });
    connect(&events, &EventBus::messageCompositionCancelled, this, [this]() {
        printMessage(AppText::CompositionCancelled);
    });
    connect(&events, &EventBus::messageSent, this, [this](const LocalMessage& message) {
        printMessage(QString(AppText::MessageSent).arg(message.id));
    });
    connect(&events, &EventBus::messageOpened, this, [this](const LocalMessage& message, const QString& plaintext) {
        m_output << QString(AppText::MessageOpened).arg(message.id) << '\n' << plaintext << '\n';
        printPrompt();
    });
    connect(&events, &EventBus::messageForwarded, this, [this](const LocalMessage& message) {
        printMessage(QString(AppText::MessageForwarded).arg(message.id));
    });
    connect(&events, &EventBus::messageRevoked, this, [this](const QString& messageId) {
        printMessage(QString(AppText::MessageRevoked).arg(messageId));
    });
    connect(&events, &EventBus::messageDeleted, this, [this](const QString& messageId) {
        printMessage(QString(AppText::MessageDeleted).arg(messageId));
    });
    connect(&events, &EventBus::messageDownloaded, this, [this](const QString& messageId, const QString& path) {
        printMessage(QString(AppText::MessageDownloaded).arg(messageId, path));
    });
    connect(&events, &EventBus::fidelityStatusUpdated, this, [this](const QString&, const QString& status) {
        printMessage(status);
    });

    printMessage(AppText::Greeting);
}

void ConsolePresenter::printPrompt() {
    m_output << AppText::Prompt << Qt::flush;
}

void ConsolePresenter::printOperation(const QString& message) {
    m_output << message << '\n' << Qt::flush;
}

void ConsolePresenter::printMessage(const QString& message) {
    m_output << message << '\n';
    printPrompt();
}

void ConsolePresenter::printError(const ClientError& error) {
    const QString message = m_showRawErrors ? error.message : safeErrorMessage(error);
    m_output << AppText::ErrorPrefix << errorCodeToString(error.code) << AppText::ErrorSeparator << message << '\n';
    printPrompt();
}

QString ConsolePresenter::safeErrorMessage(const ClientError& error) const {
    switch (error.code) {
    case ErrorCode::InvalidCommand:
        return error.message;
    case ErrorCode::InvalidConfiguration:
        return AppText::InvalidConfigurationError + AppText::DebugErrorHint;
    case ErrorCode::AuthRequired:
        return AppText::AuthRequiredError + AppText::DebugErrorHint;
    case ErrorCode::NetworkError:
        if (error.message == AppText::HttpRequestTimedOut) {
            return AppText::HttpRequestTimedOut;
        }
        return AppText::NetworkError + AppText::DebugErrorHint;
    case ErrorCode::TlsError:
        return AppText::TlsError + AppText::DebugErrorHint;
    case ErrorCode::HttpError:
        return AppText::HttpError + AppText::DebugErrorHint;
    case ErrorCode::CryptoError:
        return AppText::CryptoError + AppText::DebugErrorHint;
    case ErrorCode::TrustError:
        return AppText::TrustError + AppText::DebugErrorHint;
    case ErrorCode::StorageError:
        return AppText::StorageError + AppText::DebugErrorHint;
    case ErrorCode::NotFound:
        return AppText::NotFoundError + AppText::DebugErrorHint;
    case ErrorCode::OperationFailed:
        return AppText::OperationFailedError + AppText::DebugErrorHint;
    }
    return AppText::OperationFailedError + AppText::DebugErrorHint;
}
