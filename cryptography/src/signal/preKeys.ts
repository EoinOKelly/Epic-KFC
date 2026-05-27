import { Ed25519KeyPair } from "../ed25519";
import { PreKeyBundle, signSignedPreKey } from "./x3dh";
import { X25519KeyPair } from "../x25519";

export interface DeviceKeyMaterial {
  registrationId: number;
  deviceId: number;
  identityKeyPair: X25519KeyPair;
  identitySigningKeyPair: Ed25519KeyPair;
  signedPreKey: X25519KeyPair;
  signedPreKeyId: number;
}

export function buildPreKeyBundle(
  device: DeviceKeyMaterial,
  oneTimePreKey?: { id: number; keyPair: X25519KeyPair }
): PreKeyBundle {
  const signature = signSignedPreKey(
    device.identitySigningKeyPair.privateKey,
    device.signedPreKey.publicKey
  );

  const bundle: PreKeyBundle = {
    registrationId: device.registrationId,
    deviceId: device.deviceId,
    identityKey: device.identityKeyPair.publicKey,
    identitySigningKey: device.identitySigningKeyPair.publicKey,
    signedPreKeyId: device.signedPreKeyId,
    signedPreKey: device.signedPreKey.publicKey,
    signedPreKeySignature: signature,
  };

  if (oneTimePreKey) {
    bundle.oneTimePreKeyId = oneTimePreKey.id;
    bundle.oneTimePreKey = oneTimePreKey.keyPair.publicKey;
  }

  return bundle;
}
