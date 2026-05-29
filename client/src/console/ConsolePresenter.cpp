#include "console/ConsolePresenter.h"

#include "support/ClientConstants.h"

ConsolePresenter::ConsolePresenter(EventBus& events, QObject* parent)
    : QObject(parent)
    , m_output(stdout) {
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
        printMessage(QString(AppText::TrustFirstUse).arg(pin.userId).arg(pin.deviceId));
    });
    connect(&events, &EventBus::trustPinMatched, this, [this](const QString& userId, int deviceId) {
        printMessage(QString(AppText::TrustAlreadyMatches).arg(userId).arg(deviceId));
    });
    connect(&events, &EventBus::trustPinMismatch, this, [this](const QString& userId, int deviceId) {
        printError({ErrorCode::TrustError, QString(AppText::TrustMismatch).arg(userId).arg(deviceId)});
    });
    connect(&events, &EventBus::conversationListUpdated, this, [this](const ConversationList& conversations) {
        if (conversations.isEmpty()) {
            printMessage(AppText::EmptyConversationList);
            return;
        }
        m_output << AppText::ConversationHeader << '\n';
        for (const auto& conversation : conversations) {
            m_output << "  " << conversation.peerUserId << " device " << conversation.peerDeviceId
                     << " | messages=" << conversation.messageCount << '\n';
        }
        printPrompt();
    });
    connect(&events, &EventBus::messageListUpdated, this, [this](const MessageList& messages) {
        if (messages.isEmpty()) {
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
        if (body.isEmpty()) {
            printMessage(QString(AppText::CompositionStarted).arg(recipientUserId).arg(deviceId));
            return;
        }
        printMessage(QString(AppText::DraftLength).arg(body.size()));
    });
    connect(&events, &EventBus::messageCompositionCancelled, this, [this]() {
        printMessage(AppText::CompositionCancelled);
    });
    connect(&events, &EventBus::messageSent, this, [this](const LocalMessage& message) {
        printMessage(QString(AppText::MessageSent).arg(message.id, message.recipientUserId).arg(message.recipientDeviceId));
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

void ConsolePresenter::printMessage(const QString& message) {
    m_output << message << '\n';
    printPrompt();
}

void ConsolePresenter::printError(const ClientError& error) {
    m_output << AppText::ErrorPrefix << errorCodeToString(error.code) << AppText::ErrorSeparator << error.message << '\n';
    printPrompt();
}
