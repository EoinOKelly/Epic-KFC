#pragma once

#include "gateways/Gateways.h"

#include <QByteArray>

#include <map>

class NativeSignalCryptoProvider : public ICryptoProvider {
public:
    bool isAvailable() const;

    Result<DeviceKeyMaterial> loadOrCreateDevice(DeviceKeyMaterial existing, int deviceId) override;
    Result<std::vector<OneTimePreKey>> createOneTimePreKeys(int deviceId, int count) override;
    Result<bool> verifySignedPreKey(const PreKeyBundle& bundle) override;
    Result<EncryptedPayload> encrypt(const QString& senderUserId, const DeviceKeyMaterial& senderDevice, const PreKeyBundle& recipientBundle, const QString& plaintext) override;
    Result<QString> decrypt(const QString& currentUserId, const DeviceKeyMaterial& currentDevice, const LocalMessage& message, const std::optional<OneTimePreKey>& oneTimePreKey) override;

private:
    QByteArray randomBytes(qsizetype size) const;
    QByteArray fromBase64(const QString& value) const;
    QString toBase64(const QByteArray& value) const;
    QByteArray digest(const QByteArray& value) const;
    QByteArray hmac(const QByteArray& key, const QByteArray& data) const;
    QByteArray deriveMessageKey(const QByteArray& localPrivateKey, const QByteArray& remotePublicKey, const QByteArray& salt) const;
    QByteArray kdfX3dh(const QByteArray& dhOutputs) const;
    QByteArray firstRatchetMessageKey(const QByteArray& rootKey, const QByteArray& localRatchetPrivateKey, const QByteArray& remoteRatchetPublicKey) const;
    QByteArray cryptWithKeystream(const QByteArray& input, const QByteArray& key, const QByteArray& iv) const;
    QByteArray aadFor(int counter, int previousCounter, const QByteArray& ratchetPublicKey) const;
    QString sessionKey(const QString& userId, int deviceId) const;
    int nextCounter(const QString& userId, int deviceId);

    std::map<QString, int> m_sendCounters;
};
