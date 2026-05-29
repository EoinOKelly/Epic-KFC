#include "console/ConsoleInputWorker.h"

#include <QTextStream>

ConsoleInputWorker::ConsoleInputWorker(QObject* parent)
    : QObject(parent) {
}

ConsoleInputWorker::~ConsoleInputWorker() {
    requestStop();
    if (m_thread.joinable()) {
        m_thread.join();
    }
}

void ConsoleInputWorker::start() {
    if (m_thread.joinable()) {
        return;
    }
    m_thread = std::thread([this]() {
        readInput();
    });
}

void ConsoleInputWorker::requestStop() {
    m_stopRequested.store(true);
}

void ConsoleInputWorker::readInput() {
    QTextStream input(stdin);
    while (!m_stopRequested.load()) {
        const QString line = input.readLine();
        if (line.isNull()) {
            break;
        }
        emit lineRead(line);
    }
}
