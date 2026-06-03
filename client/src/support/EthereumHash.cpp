#include "support/EthereumHash.h"

#include <QByteArray>
#include <QDateTime>
#include <QJsonDocument>
#include <QJsonObject>

#include <array>
#include <cstdint>

namespace {
constexpr int KeccakRateBytes = 136;
constexpr int KeccakDigestBytes = 32;
constexpr int KeccakStateWords = 25;
constexpr int KeccakRounds = 24;
constexpr quint8 KeccakPaddingStart = 0x01;
constexpr quint8 KeccakPaddingEnd = 0x80;

constexpr std::array<int, KeccakStateWords> RotationOffsets{
    0, 1, 62, 28, 27,
    36, 44, 6, 55, 20,
    3, 10, 43, 25, 39,
    41, 45, 15, 21, 8,
    18, 2, 61, 56, 14
};

constexpr std::array<quint64, KeccakRounds> RoundConstants{
    0x0000000000000001ULL, 0x0000000000008082ULL, 0x800000000000808aULL,
    0x8000000080008000ULL, 0x000000000000808bULL, 0x0000000080000001ULL,
    0x8000000080008081ULL, 0x8000000000008009ULL, 0x000000000000008aULL,
    0x0000000000000088ULL, 0x0000000080008009ULL, 0x000000008000000aULL,
    0x000000008000808bULL, 0x800000000000008bULL, 0x8000000000008089ULL,
    0x8000000000008003ULL, 0x8000000000008002ULL, 0x8000000000000080ULL,
    0x000000000000800aULL, 0x800000008000000aULL, 0x8000000080008081ULL,
    0x8000000000008080ULL, 0x0000000080000001ULL, 0x8000000080008008ULL
};

quint64 rotateLeft(quint64 value, int shift) {
    if (shift == 0) {
        return value;
    }
    return (value << shift) | (value >> (64 - shift));
}

quint64 readLittleEndianWord(const QByteArray& block, int offset) {
    quint64 value = 0;
    for (int index = 0; index < 8; ++index) {
        value |= static_cast<quint64>(static_cast<quint8>(block.at(offset + index))) << (8 * index);
    }
    return value;
}

void appendLittleEndianWord(QByteArray& output, quint64 value) {
    for (int index = 0; index < 8; ++index) {
        output.append(static_cast<char>((value >> (8 * index)) & 0xff));
    }
}

void keccakPermutation(std::array<quint64, KeccakStateWords>& state) {
    for (const quint64 roundConstant : RoundConstants) {
        std::array<quint64, 5> columnParity{};
        for (int x = 0; x < 5; ++x) {
            columnParity[x] = state[x] ^ state[x + 5] ^ state[x + 10] ^ state[x + 15] ^ state[x + 20];
        }

        std::array<quint64, 5> theta{};
        for (int x = 0; x < 5; ++x) {
            theta[x] = columnParity[(x + 4) % 5] ^ rotateLeft(columnParity[(x + 1) % 5], 1);
        }
        for (int x = 0; x < 5; ++x) {
            for (int y = 0; y < 5; ++y) {
                state[x + 5 * y] ^= theta[x];
            }
        }

        std::array<quint64, KeccakStateWords> rotated{};
        for (int x = 0; x < 5; ++x) {
            for (int y = 0; y < 5; ++y) {
                const int source = x + 5 * y;
                const int destination = y + 5 * ((2 * x + 3 * y) % 5);
                rotated[destination] = rotateLeft(state[source], RotationOffsets[source]);
            }
        }

        for (int x = 0; x < 5; ++x) {
            for (int y = 0; y < 5; ++y) {
                state[x + 5 * y] = rotated[x + 5 * y] ^ ((~rotated[((x + 1) % 5) + 5 * y]) & rotated[((x + 2) % 5) + 5 * y]);
            }
        }

        state[0] ^= roundConstant;
    }
}

QByteArray keccak256(const QByteArray& input) {
    std::array<quint64, KeccakStateWords> state{};
    QByteArray padded = input;
    padded.append(static_cast<char>(KeccakPaddingStart));
    while ((padded.size() % KeccakRateBytes) != KeccakRateBytes - 1) {
        padded.append('\0');
    }
    padded.append(static_cast<char>(KeccakPaddingEnd));

    for (int offset = 0; offset < padded.size(); offset += KeccakRateBytes) {
        for (int lane = 0; lane < KeccakRateBytes / 8; ++lane) {
            state[lane] ^= readLittleEndianWord(padded, offset + lane * 8);
        }
        keccakPermutation(state);
    }

    QByteArray output;
    output.reserve(KeccakDigestBytes);
    for (int lane = 0; output.size() < KeccakDigestBytes; ++lane) {
        QByteArray word;
        appendLittleEndianWord(word, state[lane]);
        output.append(word.left(KeccakDigestBytes - output.size()));
    }
    return output;
}

QString keccakHex(const QByteArray& bytes) {
    return QString("0x%1").arg(QString::fromLatin1(keccak256(bytes).toHex()));
}

QString canonicalDateTime(const QDateTime& value) {
    if (!value.isValid()) {
        return {};
    }
    return value.toUTC().toString(Qt::ISODateWithMs).replace('Z', "+00:00");
}

QString canonicalDateTime(const LocalMessage& message) {
    if (!message.createdAtRaw.isEmpty()) {
        QString raw = message.createdAtRaw;
        if (raw.endsWith('Z')) {
            raw.chop(1);
            raw.append("+00:00");
        }
        return raw;
    }
    return canonicalDateTime(message.createdAt);
}

QByteArray canonicalMessageBytes(const LocalMessage& message) {
    QJsonObject canonical{
        {"created_at", canonicalDateTime(message)},
        {"forwarded_from_message_id", QJsonValue::Null},
        {"id", message.id},
        {"recipient_device_id", message.recipientDeviceId},
        {"recipient_user_id", message.recipientUserId},
        {"sender_device_id", message.senderDeviceId},
        {"sender_user_id", message.senderUserId},
        {"wire_payload_json", message.wirePayloadJson}
    };
    return QJsonDocument(canonical).toJson(QJsonDocument::Compact);
}
}

namespace EthereumHash {
QString recordIdForMessage(const QString& messageId) {
    return keccakHex(QString("message:%1").arg(messageId).toUtf8());
}

Result<QString> digestForMessage(const LocalMessage& message) {
    const bool hasRequiredMetadata = !message.id.isEmpty()
        && !message.senderUserId.isEmpty()
        && !message.recipientUserId.isEmpty()
        && !message.wirePayloadJson.isEmpty()
        && message.createdAt.isValid();
    if (!hasRequiredMetadata) {
        return Result<QString>::failure({ErrorCode::OperationFailed, "Message metadata is incomplete for blockchain verification."});
    }
    return Result<QString>::success(keccakHex(canonicalMessageBytes(message)));
}
}
