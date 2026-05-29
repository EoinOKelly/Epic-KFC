#include "app/SlashCommandParser.h"

#include "support/ClientConstants.h"

Result<SlashCommand> SlashCommandParser::parse(const QString& input) const {
    const QString trimmed = input.trimmed();
    if (trimmed.isEmpty()) {
        return Result<SlashCommand>::failure({
            ErrorCode::InvalidCommand,
            QString(CommandText::EmptyIgnored).arg(CommandText::HelpPrompt)
        });
    }

    const bool missingSlashPrefix = !trimmed.startsWith(CommandText::SlashPrefix);
    if (missingSlashPrefix) {
        return Result<SlashCommand>::failure({
            ErrorCode::InvalidCommand,
            QString(CommandText::MissingSlash).arg(CommandText::HelpPrompt)
        });
    }

    const int firstSpace = trimmed.indexOf(CommandText::Space);
    const bool hasArguments = firstSpace >= 0;
    int commandNameLength = -1;
    if (hasArguments) {
        commandNameLength = firstSpace - 1;
    }

    const QString commandName = trimmed.mid(1, commandNameLength).toLower();
    if (commandName.isEmpty()) {
        return Result<SlashCommand>::failure({
            ErrorCode::InvalidCommand,
            QString(CommandText::MissingName).arg(CommandText::HelpPrompt)
        });
    }

    const auto commandType = commandTypeFromName(commandName);
    if (!commandType.has_value()) {
        return Result<SlashCommand>::failure({
            ErrorCode::InvalidCommand,
            QString(CommandText::UnknownCommand).arg(commandName, CommandText::HelpPrompt)
        });
    }

    QStringList arguments;
    if (hasArguments) {
        const auto tokenized = tokenizeArguments(trimmed.mid(firstSpace + 1));
        if (tokenized.failed()) {
            return Result<SlashCommand>::failure(tokenized.error());
        }
        arguments = tokenized.value();
    }

    return Result<SlashCommand>::success({*commandType, commandName, arguments, input});
}

Result<QStringList> SlashCommandParser::tokenizeArguments(const QString& text) const {
    QStringList arguments;
    QString current;
    bool inQuote = false;
    bool escaping = false;

    for (const QChar character : text) {
        if (escaping) {
            current.append(character);
            escaping = false;
            continue;
        }

        const bool startsEscape = inQuote && character == CommandText::Escape;
        if (startsEscape) {
            escaping = true;
            continue;
        }

        const bool quoteBoundary = character == CommandText::Quote;
        if (quoteBoundary) {
            inQuote = !inQuote;
            continue;
        }

        const bool argumentBoundary = character.isSpace() && !inQuote;
        if (argumentBoundary) {
            if (!current.isEmpty()) {
                arguments.push_back(current);
                current.clear();
            }
            continue;
        }

        current.append(character);
    }

    if (escaping) {
        current.append(CommandText::Escape);
    }

    if (inQuote) {
        return Result<QStringList>::failure({ErrorCode::InvalidCommand, CommandText::UnclosedQuote});
    }

    if (!current.isEmpty()) {
        arguments.push_back(current);
    }

    return Result<QStringList>::success(arguments);
}
