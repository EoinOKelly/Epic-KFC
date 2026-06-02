#pragma once

#include "domain/Models.h"
#include "support/Result.h"

#include <QString>

#include <vector>

class SlashCommandParser {
public:
    Result<SlashCommand> parse(const QString& input) const;

private:
    Result<std::vector<QString>> tokenizeArguments(const QString& text) const;
};
