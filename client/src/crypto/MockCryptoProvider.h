#pragma once

#include "gateways/Gateways.h"

#include <string>
#include <unordered_map>

class MockCryptoProvider : public ICryptoProvider {
public:
    Result<DeviceKeyMaterial> loadOrCreateDevice(DeviceKeyMaterial existing, int deviceId) override;
    Result<std::vector<OneTimePreKey>> createOneTimePreKeys(int deviceId, int count) override;
    Result<bool> verifySignedPreKey(const PreKeyBundle& bundle) override;
    Result<EncryptedPayload> encrypt(const QString& senderUserId, const DeviceKeyMaterial& senderDevice, const PreKeyBundle& recipientBundle, const QString& plaintext) override;
    Result<QString> decrypt(const QString& currentUserId, const DeviceKeyMaterial& currentDevice, const LocalMessage& message, const std::optional<OneTimePreKey>& oneTimePreKey) override;

private:
    QString encodedMockBytes(const QString& label) const;
    QString toBase64(const QByteArray& value) const;
    std::string sessionKey(const QString& userId, int deviceId) const;
    int nextCounter(const QString& userId, int deviceId);

    std::unordered_map<std::string, int> m_sendCounters;
};
