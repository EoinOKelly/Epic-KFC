#pragma once

#include "domain/Models.h"
#include "support/Result.h"

#include <QString>

namespace EthereumHash {
QString recordIdForMessage(const QString& messageId);
Result<QString> digestForMessage(const LocalMessage& message);
}
