#include "app/ClientController.h"

#include "support/ClientConstants.h"

ClientController::ClientController(
    EventBus& events,
    const StartupConfig& config,
    SessionService& sessionService,
    KeyService& keyService,
    MessageService& messageService,
    QObject* parent)
    : QObject(parent)
    , m_events(events)
    , m_config(config)
    , m_sessionService(sessionService)
    , m_keyService(keyService)
    , m_messageService(messageService) {
    connect(&m_events, &EventBus::sessionStarted, this, [this]() {
        m_keyService.ensureDeviceKeysUploaded();
    });
}

void ClientController::handleCommand(const SlashCommand& command) {
    switch (command.type) {
    case CommandType::Help:
        emit m_events.statusMessage(AppText::Help);
        return;
    case CommandType::Logout:
        m_sessionService.logout();
        return;
    case CommandType::Whoami:
        if (const auto session = m_sessionService.currentSession(); session.has_value()) {
            emit m_events.statusMessage(QString(AppText::LoggedInAs).arg(session->user.username, session->user.id));
        } else {
            emit m_events.statusMessage(AppText::NotLoggedIn);
        }
        return;
    case CommandType::Status:
        if (m_config.mode == ClientMode::Real) {
            emit m_events.statusMessage(QString(AppText::RealStatus).arg(m_config.apiUrl));
        } else {
            emit m_events.statusMessage(AppText::MockStatus);
        }
        return;
    case CommandType::Conversations:
        m_messageService.listConversations();
        return;
    case CommandType::Inbox:
    case CommandType::Sync:
        m_messageService.listReceived();
        return;
    case CommandType::Sent:
        m_messageService.listSent();
        return;
    case CommandType::Read:
        if (command.arguments.size() == 1) {
            m_messageService.read(command.arguments.at(0));
        }
        return;
    case CommandType::Forward:
        if (command.arguments.size() == 2) {
            m_messageService.forward(command.arguments.at(0), command.arguments.at(1));
        }
        return;
    case CommandType::Revoke:
        if (command.arguments.size() == 1) {
            m_messageService.revoke(command.arguments.at(0));
        }
        return;
    case CommandType::DeleteMessage:
        if (command.arguments.size() == 1) {
            m_messageService.deleteMessage(command.arguments.at(0));
        }
        return;
    case CommandType::Download:
        if (command.arguments.size() == 2) {
            m_messageService.download(command.arguments.at(0), command.arguments.at(1));
        }
        return;
    case CommandType::Trust:
        if (command.arguments.size() == 1) {
            m_keyService.trustUsername(command.arguments.at(0));
        }
        return;
    case CommandType::Verify:
        if (command.arguments.size() == 1) {
            m_messageService.verify(command.arguments.at(0));
        }
        return;
    case CommandType::Cancel:
        emit m_events.statusMessage(AppText::NoComposition);
        return;
    case CommandType::Exit:
        emit m_events.exitRequested();
        return;
    case CommandType::Register:
    case CommandType::Login:
    case CommandType::Msg:
    case CommandType::Send:
        return;
    }
}

void ClientController::registerUser(const QString& username, const QString& email, const QString& password) {
    m_sessionService.registerUser(username, email, password);
}

void ClientController::login(const QString& usernameOrEmail, const QString& password) {
    m_sessionService.login(usernameOrEmail, password);
}

void ClientController::beginMessageComposition(const QString& recipientUsername) {
    emit m_events.messagePrepared(recipientUsername, m_config.deviceId, {});
}

void ClientController::submitComposedMessage(const QString& recipientUsername, const QString& body) {
    if (body.trimmed().isEmpty()) {
        emit m_events.commandFailed({ErrorCode::InvalidCommand, AppText::EmptyMessage});
        return;
    }
    m_messageService.send(recipientUsername, body);
}

void ClientController::cancelComposition() {
    emit m_events.messageCompositionCancelled();
}

