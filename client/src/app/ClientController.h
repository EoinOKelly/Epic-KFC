#pragma once

#include "app/EventBus.h"
#include "domain/Models.h"
#include "services/Services.h"

#include <QObject>

class ClientController : public QObject {
    Q_OBJECT

public:
    ClientController(
        EventBus& events,
        const StartupConfig& config,
        SessionService& sessionService,
        KeyService& keyService,
        MessageService& messageService,
        QObject* parent = nullptr);

    void handleCommand(const SlashCommand& command);
    void registerUser(const QString& username, const QString& email, const QString& password);
    void login(const QString& usernameOrEmail, const QString& password);
    void beginMessageComposition(const QString& recipientUsername);
    void submitComposedMessage(const QString& recipientUsername, const QString& body);
    void cancelComposition();

private:
    EventBus& m_events;
    StartupConfig m_config;
    SessionService& m_sessionService;
    KeyService& m_keyService;
    MessageService& m_messageService;
};
