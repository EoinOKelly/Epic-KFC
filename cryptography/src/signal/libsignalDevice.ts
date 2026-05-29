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

/** JSON shape from GET /api/v1/keys/users/{id}/devices/{id}/prekey-bundle */
export interface ApiPreKeyBundleResponse {
  registrationId: number;
  deviceId: number;
  identityKey: string;
  signedPreKeyId: number;
  signedPreKey: string;
  signedPreKeySignature: string;
  oneTimePreKeyId?: number | null;
  oneTimePreKey?: string | null;
}

export function preKeyBundleFromApiResponse(api: ApiPreKeyBundleResponse): DeviceType {
  return publicBundleFromDb({
    user_id: "",
    device_id: api.deviceId,
    registration_id: api.registrationId,
    identity_key_public_b64: api.identityKey,
    signed_prekey_id: api.signedPreKeyId,
    signed_prekey_public_b64: api.signedPreKey,
    signed_prekey_signature_b64: api.signedPreKeySignature,
    signed_prekey_created_at: "",
    one_time_prekey_id: api.oneTimePreKeyId ?? null,
    one_time_prekey_public_b64: api.oneTimePreKey ?? null,
  });
}

/** Maps deviceToDbRows output to PUT /api/v1/keys/devices/{device_id} body. */
export function deviceKeyUploadPayloadFromRow(deviceKeys: DeviceKeysRow): {
  device_id: number;
  registration_id: number;
  identity_key_public_b64: string;
  identity_signing_public_b64: string;
  signed_prekey_id: number;
  signed_prekey_public_b64: string;
  signed_prekey_signature_b64: string;
} {
  return {
    device_id: deviceKeys.device_id,
    registration_id: deviceKeys.registration_id,
    identity_key_public_b64: deviceKeys.identity_key_public_b64,
    identity_signing_public_b64: deviceKeys.identity_key_public_b64,
    signed_prekey_id: deviceKeys.signed_prekey_id,
    signed_prekey_public_b64: deviceKeys.signed_prekey_public_b64,
    signed_prekey_signature_b64: deviceKeys.signed_prekey_signature_b64,
  };
}
