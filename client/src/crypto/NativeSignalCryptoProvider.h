#pragma once

#include "gateways/Gateways.h"

#include <QByteArray>
#include <QHash>

class NativeSignalCryptoProvider : public ICryptoProvider {
public:
    Result<DeviceKeyMaterial> loadOrCreateDevice(DeviceKeyMaterial existing, int deviceId) override;
    Result<QList<OneTimePreKey>> createOneTimePreKeys(int deviceId, int count) override;
    Result<bool> verifySignedPreKey(const PreKeyBundle& bundle) override;
    Result<EncryptedPayload> encrypt(const QString& senderUserId, const DeviceKeyMaterial& senderDevice, const PreKeyBundle& recipientBundle, const QString& plaintext) override;
    Result<QString> decrypt(const QString& currentUserId, const DeviceKeyMaterial& currentDevice, const LocalMessage& message) override;

private:
    QByteArray randomBytes(qsizetype size) const;
    QByteArray fromBase64(const QString& value) const;
    QString toBase64(const QByteArray& value) const;
    QByteArray digest(const QByteArray& value) const;
    QByteArray hmac(const QByteArray& key, const QByteArray& data) const;
    QByteArray deriveMessageKey(const QByteArray& localPrivateKey, const QByteArray& remotePublicKey, const QByteArray& salt) const;
    QByteArray cryptWithKeystream(const QByteArray& input, const QByteArray& key, const QByteArray& iv) const;
    QByteArray aadFor(int counter, int previousCounter, const QByteArray& ratchetPublicKey) const;
    QString sessionKey(const QString& userId, int deviceId) const;
    int nextCounter(const QString& userId, int deviceId);

    QHash<QString, int> m_sendCounters;
};
