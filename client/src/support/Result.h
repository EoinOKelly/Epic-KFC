#pragma once

#include "domain/Models.h"

#include <optional>
#include <utility>

template <typename T>
class Result {
public:
    static Result success(T value) {
        return Result(std::move(value));
    }

    static Result failure(ClientError error) {
        return Result(std::move(error));
    }

    bool succeeded() const {
        return m_value.has_value();
    }

    bool failed() const {
        return !succeeded();
    }

    const T& value() const {
        return *m_value;
    }

    T& value() {
        return *m_value;
    }

    const ClientError& error() const {
        return *m_error;
    }

private:
    explicit Result(T value)
        : m_value(std::move(value)) {
    }

    explicit Result(ClientError error)
        : m_error(std::move(error)) {
    }

    std::optional<T> m_value;
    std::optional<ClientError> m_error;
};
