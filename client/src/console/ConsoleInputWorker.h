#pragma once

#include <QObject>

#include <atomic>
#include <thread>

class ConsoleInputWorker : public QObject {
    Q_OBJECT

public:
    explicit ConsoleInputWorker(QObject* parent = nullptr);
    ~ConsoleInputWorker() override;

    void start();
    void requestStop();

signals:
    void lineRead(QString line);

private:
    void readInput();

    std::atomic_bool m_stopRequested{false};
    std::thread m_thread;
};
