#pragma once

#include "app/SlashCommandParser.h"
#include "domain/Models.h"

#include <QObject>

#include <vector>

class ClientController;
class EventBus;

class CommandRouter : public QObject {
    Q_OBJECT

public:
    CommandRouter(EventBus& events, ClientController& controller, QObject* parent = nullptr);

public slots:
    void handleLine(const QString& line);

private:
    enum class InputMode {
        Command,
        RegisterPassword,
        LoginPassword,
        MessageComposition
    };

    void handleCommandMode(const QString& line);
    void handleRegisterPassword(const QString& line);
    void handleLoginPassword(const QString& line);
    void handleMessageComposition(const QString& line);
    bool commandHasArgumentCount(const SlashCommand& command, int minimum, int maximum = -1);

    EventBus& m_events;
    ClientController& m_controller;
    SlashCommandParser m_parser;
    InputMode m_inputMode{InputMode::Command};
    QString m_pendingUsername;
    QString m_pendingEmail;
    QString m_pendingLoginIdentifier;
    QString m_compositionRecipientUsername;
    std::vector<QString> m_compositionLines;
};
