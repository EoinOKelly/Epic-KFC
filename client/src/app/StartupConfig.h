#pragma once

#include "domain/Models.h"
#include "support/Result.h"

#include <QStringList>

class StartupConfigParser {
public:
    Result<StartupConfig> parse(const QStringList& arguments) const;
};
