#pragma once

#include "domain/Models.h"

#include <QObject>

class EventBus : public QObject {
    Q_OBJECT

public:
    explicit EventBus(QObject* parent = nullptr);

signals:
    void slashCommandReceived(SlashCommand command);
    void statusMessage(QString message);
    void commandFailed(ClientError error);
    void sessionStarted(UserProfile user);
    void sessionEnded();
    void deviceKeysReady(int deviceId);
    void trustPinCreated(TrustPin pin);
    void trustPinMatched(QString userId, int deviceId);
    void trustPinMismatch(QString userId, int deviceId);
    void conversationListUpdated(ConversationList conversations);
    void messageListUpdated(MessageList messages);
    void messageReceived(LocalMessage message);
    void messagePrepared(QString recipientUserId, int deviceId, QString currentBody);
    void messageCompositionCancelled();
    void messageSent(LocalMessage message);
    void messageOpened(LocalMessage message, QString plaintext);
    void messageForwarded(LocalMessage message);
    void messageRevoked(QString messageId);
    void messageDeleted(QString messageId);
    void messageDownloaded(QString messageId, QString path);
    void fidelityStatusUpdated(QString messageId, QString status);
    void backendUnavailable(ClientError error);
    void cryptoOperationFailed(ClientError error);
    void exitRequested();
};
