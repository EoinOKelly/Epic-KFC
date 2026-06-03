#include "app/CommandRouter.h"

#include "app/ClientController.h"
#include "app/EventBus.h"
#include "support/ClientConstants.h"

#include <set>

namespace {
QString joinedLines(const std::vector<QString>& lines) {
    QString result;
    for (const auto& line : lines) {
        if (!result.isEmpty()) {
            result.append('\n');
        }
        result.append(line);
    }
    return result;
}

QString joinedArguments(const std::vector<QString>& arguments, std::size_t firstIndex) {
    QString result;
    for (std::size_t index = firstIndex; index < arguments.size(); ++index) {
        if (!result.isEmpty()) {
            result.append(' ');
        }
        result.append(arguments.at(index));
    }
    return result;
}

QString withoutConversationPromptEcho(QString line, const QString& username) {
    if (username.isEmpty()) {
        return line;
    }

    const QString prompt = QString(AppText::ConversationPrompt).arg(username);
    if (line.startsWith(prompt)) {
        return line.mid(prompt.size()).trimmed();
    }

    const QString compactPrompt = QString("[%1] >").arg(username);
    if (!line.startsWith(compactPrompt)) {
        return line;
    }

    QString stripped = line.mid(compactPrompt.size()).trimmed();
    constexpr ushort RightArrowCodePoint = 0x2192;
    if (stripped.startsWith(QChar(RightArrowCodePoint))) {
        stripped.remove(0, 1);
    }
    return stripped.trimmed();
}

bool isClientOutputEcho(const QString& line) {
    return line.trimmed() == AppText::SendingMessage;
}

const std::set<CommandType>& zeroArgumentCommands() {
    static const std::set<CommandType> commands{
        CommandType::Help,
        CommandType::Logout,
        CommandType::Whoami,
        CommandType::Status,
        CommandType::Conversations,
        CommandType::Inbox,
        CommandType::Sent,
        CommandType::Sync,
        CommandType::Cancel,
        CommandType::Back,
        CommandType::Exit,
    };
    return commands;
}

const std::set<CommandType>& oneArgumentCommands() {
    static const std::set<CommandType> commands{
        CommandType::Revoke,
        CommandType::DeleteMessage,
        CommandType::Verify,
        CommandType::Trust,
    };
    return commands;
}
}

CommandRouter::CommandRouter(EventBus& events, ClientController& controller, QObject* parent)
    : QObject(parent)
    , m_events(events)
    , m_controller(controller) {
    connect(&m_events, &EventBus::operationStarted, this, [this]() {
        m_operationInProgress = true;
    });
    connect(&m_events, &EventBus::statusMessage, this, [this]() {
        m_operationInProgress = false;
    });
    connect(&m_events, &EventBus::commandFailed, this, [this]() {
        m_operationInProgress = false;
    });
    connect(&m_events, &EventBus::sessionStarted, this, [this]() {
        m_operationInProgress = false;
    });
    connect(&m_events, &EventBus::sessionEnded, this, [this]() {
        m_activeConversationUsername.clear();
        m_operationInProgress = false;
    });
    connect(&m_events, &EventBus::conversationTargetChanged, this, [this](const QString& username) {
        m_activeConversationUsername = username;
    });
    connect(&m_events, &EventBus::trustPinCreated, this, [this]() {
        m_operationInProgress = false;
    });
    connect(&m_events, &EventBus::trustPinMatched, this, [this]() {
        m_operationInProgress = false;
    });
    connect(&m_events, &EventBus::trustPinMismatch, this, [this]() {
        m_operationInProgress = false;
    });
    connect(&m_events, &EventBus::conversationListUpdated, this, [this]() {
        m_operationInProgress = false;
    });
    connect(&m_events, &EventBus::unreadInboxUpdated, this, [this]() {
        m_operationInProgress = false;
    });
    connect(&m_events, &EventBus::conversationLogOpened, this, [this]() {
        m_operationInProgress = false;
    });
    connect(&m_events, &EventBus::messageListUpdated, this, [this]() {
        m_operationInProgress = false;
    });
    connect(&m_events, &EventBus::messageSent, this, [this]() {
        m_operationInProgress = false;
    });
    connect(&m_events, &EventBus::messageForwarded, this, [this]() {
        m_operationInProgress = false;
    });
    connect(&m_events, &EventBus::messageRevoked, this, [this]() {
        m_operationInProgress = false;
    });
    connect(&m_events, &EventBus::messageDeleted, this, [this]() {
        m_operationInProgress = false;
    });
    connect(&m_events, &EventBus::messageDownloaded, this, [this]() {
        m_operationInProgress = false;
    });
    connect(&m_events, &EventBus::fidelityStatusUpdated, this, [this]() {
        m_operationInProgress = false;
    });
    connect(&m_events, &EventBus::backendUnavailable, this, [this]() {
        m_operationInProgress = false;
    });
    connect(&m_events, &EventBus::cryptoOperationFailed, this, [this]() {
        m_operationInProgress = false;
    });
}

void CommandRouter::handleLine(const QString& line) {
    const bool commandInputWhileBusy = m_inputMode == InputMode::Command && m_operationInProgress;
    if (commandInputWhileBusy) {
        if (!line.trimmed().isEmpty()) {
            emit m_events.operationStarted(AppText::OperationInProgress);
        }
        return;
    }

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
    const QString trimmed = line.trimmed();
    if (trimmed.isEmpty()) {
        return;
    }

    const bool activeConversationText = !m_activeConversationUsername.isEmpty()
        && !trimmed.startsWith(CommandText::SlashPrefix);
    if (activeConversationText) {
        const QString body = withoutConversationPromptEcho(line, m_activeConversationUsername);
        if (!body.trimmed().isEmpty() && !isClientOutputEcho(body)) {
            m_controller.sendMessage(m_activeConversationUsername, body);
        }
        return;
    }

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
        handleMsgCommand(command);
        return;
    case CommandType::Send:
        handleSendCommand(command);
        return;
    default:
        break;
    }

    if (zeroArgumentCommands().contains(command.type)) {
        if (commandHasArgumentCount(command, 0, 0)) {
            m_controller.handleCommand(command);
        }
        return;
    }

    if (oneArgumentCommands().contains(command.type)) {
        if (commandHasArgumentCount(command, 1, 1)) {
            m_controller.handleCommand(command);
        }
        return;
    }

    switch (command.type) {
    case CommandType::Read:
        if (commandHasArgumentCount(command, 1, 2)) {
            m_controller.handleCommand(command);
        }
        return;
    case CommandType::Forward:
        if (commandHasArgumentCount(command, 2, 2)) {
            m_controller.handleCommand(command);
        }
        return;
    case CommandType::Download:
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
            joinedLines(m_compositionLines));
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

    const bool backRequested = trimmed.compare(CommandText::BackCommand, Qt::CaseInsensitive) == 0;
    if (backRequested) {
        m_inputMode = InputMode::Command;
        m_compositionLines.clear();
        m_controller.handleCommand({CommandType::Back, CommandNames::Back.toStdString(), {}, line});
        return;
    }

    const QString bodyLine = withoutConversationPromptEcho(line, m_compositionRecipientUsername);
    if (bodyLine.trimmed().isEmpty() || isClientOutputEcho(bodyLine)) {
        return;
    }

    m_compositionLines.push_back(bodyLine);
    emit m_events.messagePrepared(
        m_compositionRecipientUsername,
        DefaultDeviceId,
        joinedLines(m_compositionLines));
}

void CommandRouter::handleMsgCommand(const SlashCommand& command) {
    if (!commandHasArgumentCount(command, 1)) {
        return;
    }

    const QString username = command.arguments.at(0);
    const QString body = joinedArguments(command.arguments, 1);
    if (body.isEmpty()) {
        m_controller.openConversation(username);
        return;
    }

    m_controller.sendMessage(username, body);
}

void CommandRouter::handleSendCommand(const SlashCommand& command) {
    const bool hasActiveConversation = !m_activeConversationUsername.isEmpty();
    if (hasActiveConversation) {
        if (command.arguments.empty()) {
            m_compositionRecipientUsername = m_activeConversationUsername;
            m_compositionLines.clear();
            m_inputMode = InputMode::MessageComposition;
            m_controller.beginMessageComposition(m_compositionRecipientUsername);
            return;
        }

        m_controller.sendMessage(m_activeConversationUsername, joinedArguments(command.arguments, 0));
        return;
    }

    if (!commandHasArgumentCount(command, 1)) {
        return;
    }

    if (command.arguments.size() > 1) {
        m_controller.sendMessage(command.arguments.at(0), joinedArguments(command.arguments, 1));
        return;
    }

    m_compositionRecipientUsername = command.arguments.at(0);
    m_compositionLines.clear();
    m_inputMode = InputMode::MessageComposition;
    m_controller.beginMessageComposition(m_compositionRecipientUsername);
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
        QString(CommandText::ArgumentCount).arg(QString::fromStdString(command.name), expected)
    });
    return false;
}

