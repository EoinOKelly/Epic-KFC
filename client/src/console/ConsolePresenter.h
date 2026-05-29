#pragma once

#include "app/EventBus.h"

#include <QObject>
#include <QTextStream>

class ConsolePresenter : public QObject {
    Q_OBJECT

public:
    explicit ConsolePresenter(EventBus& events, QObject* parent = nullptr);

private:
    void printPrompt();
    void printMessage(const QString& message);
    void printError(const ClientError& error);

    QTextStream m_output;
};
