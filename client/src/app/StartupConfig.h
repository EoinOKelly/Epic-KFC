#pragma once

#include "domain/Models.h"
#include "support/Result.h"

#include <vector>

class StartupConfigParser {
public:
    Result<StartupConfig> parse(const std::vector<QString>& arguments) const;
};
