#pragma once

#include "app/EventBus.h"

#include <QObject>
#include <QTextStream>

class ConsolePresenter : public QObject {
    Q_OBJECT

public:
    explicit ConsolePresenter(EventBus& events, bool showRawErrors = false, QObject* parent = nullptr);

private:
    void printPrompt();
    void printOperation(const QString& message);
    void printMessage(const QString& message);
    void printError(const ClientError& error);
    QString safeErrorMessage(const ClientError& error) const;

    QTextStream m_output;
    bool m_showRawErrors{false};
};
