import "./nodeSetup";
import {
  DeviceType,
  KeyHelper,
  SignedPublicPreKeyType,
} from "@privacyresearch/libsignal-protocol-typescript";
import { toBase64 } from "../bufferUtils";
import { DeviceKeysRow, OneTimePreKeyRow, StoredDeviceKeysRow } from "../storageSchema";
import { InMemoryProtocolStore } from "./signalProtocolStore";

export interface GeneratedDevice {
  userId: string;
  deviceId: number;
  registrationId: number;
  identityKeyPair: { pubKey: ArrayBuffer; privKey: ArrayBuffer };
  store: InMemoryProtocolStore;
  signedPreKeyId: number;
  oneTimePreKeyId?: number;
  signedPreKeyPublic: SignedPublicPreKeyType;
  oneTimePreKeyPublic?: { keyId: number; publicKey: ArrayBuffer };
}

export async function generateDevice(userId: string, deviceId: number): Promise<GeneratedDevice> {
  const registrationId = KeyHelper.generateRegistrationId();
  const identityKeyPair = await KeyHelper.generateIdentityKeyPair();
  const store = new InMemoryProtocolStore(identityKeyPair, registrationId);

  const oneTimePreKeyId = 1;
  const preKey = await KeyHelper.generatePreKey(oneTimePreKeyId);
  await store.storePreKey(oneTimePreKeyId, preKey.keyPair);

  const signedPreKeyId = 1;
  const signedPreKey = await KeyHelper.generateSignedPreKey(identityKeyPair, signedPreKeyId);
  await store.storeSignedPreKey(signedPreKeyId, signedPreKey.keyPair);

  const signedPreKeyPublic: SignedPublicPreKeyType = {
    keyId: signedPreKeyId,
    publicKey: signedPreKey.keyPair.pubKey,
    signature: signedPreKey.signature,
  };

  return {
    userId,
    deviceId,
    registrationId,
    identityKeyPair,
    store,
    signedPreKeyId,
    oneTimePreKeyId,
    signedPreKeyPublic,
    oneTimePreKeyPublic: { keyId: oneTimePreKeyId, publicKey: preKey.keyPair.pubKey },
  };
}

export function deviceToPublicBundle(device: GeneratedDevice): DeviceType {
  return {
    registrationId: device.registrationId,
    identityKey: device.identityKeyPair.pubKey,
    signedPreKey: device.signedPreKeyPublic,
    preKey: device.oneTimePreKeyPublic,
  };
}

export async function deviceToDbRows(device: GeneratedDevice): Promise<{
  deviceKeys: DeviceKeysRow;
  oneTimePreKeys: OneTimePreKeyRow[];
}> {
  const deviceKeys: DeviceKeysRow = {
    user_id: device.userId,
    device_id: device.deviceId,
    registration_id: device.registrationId,
    identity_key_public_b64: toBase64(Buffer.from(device.identityKeyPair.pubKey)),
    signed_prekey_id: device.signedPreKeyId,
    signed_prekey_public_b64: toBase64(Buffer.from(device.signedPreKeyPublic.publicKey)),
    signed_prekey_signature_b64: toBase64(Buffer.from(device.signedPreKeyPublic.signature)),
    signed_prekey_created_at: new Date().toISOString(),
  };

  const oneTimePreKeys: OneTimePreKeyRow[] = [];
  if (device.oneTimePreKeyPublic) {
    oneTimePreKeys.push({
      user_id: device.userId,
      device_id: device.deviceId,
      prekey_id: device.oneTimePreKeyPublic.keyId,
      prekey_public_b64: toBase64(Buffer.from(device.oneTimePreKeyPublic.publicKey)),
      used_at: null,
    });
  }

  return { deviceKeys, oneTimePreKeys };
}

export function publicBundleFromDb(row: StoredDeviceKeysRow): DeviceType {
  const bundle: DeviceType = {
    registrationId: row.registration_id,
    identityKey: Buffer.from(row.identity_key_public_b64, "base64").buffer,
    signedPreKey: {
      keyId: row.signed_prekey_id,
      publicKey: Buffer.from(row.signed_prekey_public_b64, "base64").buffer,
      signature: Buffer.from(row.signed_prekey_signature_b64, "base64").buffer,
    },
  };

  if (row.one_time_prekey_id != null && row.one_time_prekey_public_b64) {
    bundle.preKey = {
      keyId: row.one_time_prekey_id,
      publicKey: Buffer.from(row.one_time_prekey_public_b64, "base64").buffer,
    };
  }

  return bundle;
}
