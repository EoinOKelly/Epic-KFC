#include "app/CommandRouter.h"

#include "app/ClientController.h"
#include "app/EventBus.h"
#include "support/ClientConstants.h"

CommandRouter::CommandRouter(EventBus& events, ClientController& controller, QObject* parent)
    : QObject(parent)
    , m_events(events)
    , m_controller(controller) {
}

void CommandRouter::handleLine(const QString& line) {
    switch (m_inputMode) {
    case InputMode::Command:
        handleCommandMode(line);
        return;
    case InputMode::RegisterPassword:
        handleRegisterPassword(line);
        return;
    case InputMode::LoginPassword:
        handleLoginPassword(line);
        return;
    case InputMode::MessageComposition:
        handleMessageComposition(line);
        return;
    }
}

void CommandRouter::handleCommandMode(const QString& line) {
    const auto parsed = m_parser.parse(line);
    if (parsed.failed()) {
        emit m_events.commandFailed(parsed.error());
        return;
    }

    const SlashCommand command = parsed.value();
    emit m_events.slashCommandReceived(command);
    switch (command.type) {
    case CommandType::Register:
        if (commandHasArgumentCount(command, 2, 2)) {
            m_pendingUsername = command.arguments.at(0);
            m_pendingEmail = command.arguments.at(1);
            m_inputMode = InputMode::RegisterPassword;
            emit m_events.statusMessage("Enter registration password.");
        }
        return;
    case CommandType::Login:
        if (commandHasArgumentCount(command, 1, 1)) {
            m_pendingLoginIdentifier = command.arguments.at(0);
            m_inputMode = InputMode::LoginPassword;
            emit m_events.statusMessage("Enter login password.");
        }
        return;
    case CommandType::Msg:
    case CommandType::Send:
        if (commandHasArgumentCount(command, 1, 1)) {
            m_compositionRecipientUsername = command.arguments.at(0);
            m_compositionLines.clear();
            m_inputMode = InputMode::MessageComposition;
            m_controller.beginMessageComposition(m_compositionRecipientUsername);
        }
        return;
    case CommandType::Help:
    case CommandType::Logout:
    case CommandType::Whoami:
    case CommandType::Status:
    case CommandType::Conversations:
    case CommandType::Inbox:
    case CommandType::Sent:
    case CommandType::Sync:
    case CommandType::Cancel:
    case CommandType::Exit:
        if (commandHasArgumentCount(command, 0, 0)) {
            m_controller.handleCommand(command);
        }
        return;
    case CommandType::Read:
    case CommandType::Revoke:
    case CommandType::DeleteMessage:
    case CommandType::Verify:
        if (commandHasArgumentCount(command, 1, 1)) {
            m_controller.handleCommand(command);
        }
        return;
    case CommandType::Forward:
        if (commandHasArgumentCount(command, 2, 2)) {
            m_controller.handleCommand(command);
        }
        return;
    case CommandType::Download:
        if (commandHasArgumentCount(command, 2, 2)) {
            m_controller.handleCommand(command);
        }
        return;
    case CommandType::Trust:
        if (commandHasArgumentCount(command, 1, 1)) {
            m_controller.handleCommand(command);
        }
        return;
    default:
        m_controller.handleCommand(command);
        return;
    }
}

void CommandRouter::handleRegisterPassword(const QString& line) {
    m_inputMode = InputMode::Command;
    m_controller.registerUser(m_pendingUsername, m_pendingEmail, line);
    m_pendingUsername.clear();
    m_pendingEmail.clear();
}

void CommandRouter::handleLoginPassword(const QString& line) {
    m_inputMode = InputMode::Command;
    m_controller.login(m_pendingLoginIdentifier, line);
    m_pendingLoginIdentifier.clear();
}

void CommandRouter::handleMessageComposition(const QString& line) {
    const QString trimmed = line.trimmed();
    const bool submitRequested = trimmed.compare(CommandText::SubmitCommand, Qt::CaseInsensitive) == 0;
    if (submitRequested) {
        m_inputMode = InputMode::Command;
        m_controller.submitComposedMessage(
            m_compositionRecipientUsername,
            m_compositionLines.join('\n'));
        m_compositionLines.clear();
        return;
    }

    const bool cancelRequested = trimmed.compare(CommandText::CancelCommand, Qt::CaseInsensitive) == 0;
    if (cancelRequested) {
        m_inputMode = InputMode::Command;
        m_compositionLines.clear();
        m_controller.cancelComposition();
        return;
    }

    m_compositionLines.push_back(line);
    emit m_events.messagePrepared(
        m_compositionRecipientUsername,
        DefaultDeviceId,
        m_compositionLines.join('\n'));
}

bool CommandRouter::commandHasArgumentCount(const SlashCommand& command, int minimum, int maximum) {
    const int count = command.arguments.size();
    const bool tooFew = count < minimum;
    const bool hasMaximum = maximum >= 0;
    const bool tooMany = hasMaximum && count > maximum;
    if (!tooFew && !tooMany) {
        return true;
    }

    QString expected = QString(CommandText::AtLeast).arg(minimum);
    if (hasMaximum && minimum == maximum) {
        expected = QString(CommandText::Exactly).arg(minimum);
    }

    emit m_events.commandFailed({
        ErrorCode::InvalidCommand,
        QString(CommandText::ArgumentCount).arg(command.name, expected)
    });
    return false;
}

