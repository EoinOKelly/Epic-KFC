import { assertKeyLength } from "../bufferUtils";
import { verifyEd25519 } from "../ed25519";
import { kdfX3dhSharedSecret } from "./signalKdf";
import { generateX25519KeyPair, x25519Dh, X25519KeyPair } from "../x25519";
import { signEd25519 } from "../ed25519";

export interface PreKeyBundle {
  registrationId: number;
  deviceId: number;
  identityKey: Buffer;
  identitySigningKey: Buffer;
  signedPreKeyId: number;
  signedPreKey: Buffer;
  signedPreKeySignature: Buffer;
  oneTimePreKeyId?: number;
  oneTimePreKey?: Buffer;
}

export interface X3dhInitResult {
  sharedSecret: Buffer;
  ephemeralKeyPair: X25519KeyPair;
  /** Set when a one-time pre-key was used — server should mark it consumed. */
  consumedOneTimePreKeyId?: number;
}

function validateBundle(bundle: PreKeyBundle): void {
  assertKeyLength(bundle.identityKey, 32, "identityKey");
  assertKeyLength(bundle.identitySigningKey, 32, "identitySigningKey");
  assertKeyLength(bundle.signedPreKey, 32, "signedPreKey");
  if (bundle.oneTimePreKey) assertKeyLength(bundle.oneTimePreKey, 32, "oneTimePreKey");
}

export function x3dhInitiate(
  identityKeyPair: X25519KeyPair,
  remoteBundle: PreKeyBundle
): X3dhInitResult {
  validateBundle(remoteBundle);
  assertKeyLength(identityKeyPair.privateKey, 32, "identity private key");

  if (
    !verifyEd25519(
      remoteBundle.identitySigningKey,
      remoteBundle.signedPreKey,
      remoteBundle.signedPreKeySignature
    )
  ) {
    throw new Error("x3dh: invalid signed pre-key signature");
  }

  const ephemeralKeyPair = generateX25519KeyPair();
  const dhOutputs = [
    x25519Dh(identityKeyPair.privateKey, remoteBundle.signedPreKey),
    x25519Dh(ephemeralKeyPair.privateKey, remoteBundle.identityKey),
    x25519Dh(ephemeralKeyPair.privateKey, remoteBundle.signedPreKey),
  ];

  let consumedOneTimePreKeyId: number | undefined;
  if (remoteBundle.oneTimePreKey) {
    dhOutputs.push(x25519Dh(ephemeralKeyPair.privateKey, remoteBundle.oneTimePreKey));
    consumedOneTimePreKeyId = remoteBundle.oneTimePreKeyId;
  }

  const salt = Buffer.alloc(32, 0);
  return {
    sharedSecret: kdfX3dhSharedSecret(dhOutputs, salt),
    ephemeralKeyPair,
    consumedOneTimePreKeyId,
  };
}

export function x3dhRespond(
  identityKeyPair: X25519KeyPair,
  signedPreKey: X25519KeyPair,
  oneTimePreKey: X25519KeyPair | null,
  initiatorIdentityKey: Buffer,
  initiatorEphemeralKey: Buffer
): Buffer {
  assertKeyLength(initiatorIdentityKey, 32, "initiator identity key");
  assertKeyLength(initiatorEphemeralKey, 32, "initiator ephemeral key");

  const dhOutputs = [
    x25519Dh(signedPreKey.privateKey, initiatorIdentityKey),
    x25519Dh(identityKeyPair.privateKey, initiatorEphemeralKey),
    x25519Dh(signedPreKey.privateKey, initiatorEphemeralKey),
  ];

  if (oneTimePreKey) {
    dhOutputs.push(x25519Dh(oneTimePreKey.privateKey, initiatorEphemeralKey));
  }

  return kdfX3dhSharedSecret(dhOutputs, Buffer.alloc(32, 0));
}

export function signSignedPreKey(
  identitySigningPrivateKey: Buffer,
  signedPreKeyPublic: Buffer
): Buffer {
  return signEd25519(identitySigningPrivateKey, signedPreKeyPublic);
}

export function verifySignedPreKey(
  identitySigningPublicKey: Buffer,
  signedPreKeyPublic: Buffer,
  signature: Buffer
): void {
  if (!verifyEd25519(identitySigningPublicKey, signedPreKeyPublic, signature)) {
    throw new Error("x3dh: invalid signed pre-key signature");
  }
}
