#pragma once

#include "domain/Models.h"
#include "support/Result.h"

#include <QString>
#include <QStringList>

class SlashCommandParser {
public:
    Result<SlashCommand> parse(const QString& input) const;

private:
    Result<QStringList> tokenizeArguments(const QString& text) const;
};
