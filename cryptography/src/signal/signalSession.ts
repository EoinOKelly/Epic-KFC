import {
  createRatchetState,
  DoubleRatchetState,
  ratchetDecrypt,
  ratchetEncrypt,
  SignalWireMessage,
} from "./doubleRatchet";
import { PreKeyBundle, x3dhInitiate, x3dhRespond } from "./x3dh";
import { X25519KeyPair } from "../x25519";

export const SIGNAL_PROTOCOL = {
  keyAgreement: "X3DH",
  ratchet: "Double Ratchet",
  payload: "AES-256-GCM",
  note: "Ratchet KDF per Signal spec; payload uses AES-256-GCM (brief AEAD requirement, not Signal's CBC+HMAC).",
} as const;

export interface SignalInitiatorSession {
  identityKeyPair: X25519KeyPair;
  x3dhEphemeral: X25519KeyPair;
  ratchet: DoubleRatchetState;
  remoteSignedPreKey: Buffer;
  consumedOneTimePreKeyId?: number;
}

export interface SignalResponderSession {
  identityKeyPair: X25519KeyPair;
  signedPreKey: X25519KeyPair;
  oneTimePreKey: X25519KeyPair | null;
  ratchet: DoubleRatchetState;
}

export function createInitiatorSession(
  identityKeyPair: X25519KeyPair,
  remoteBundle: PreKeyBundle
): SignalInitiatorSession {
  const { sharedSecret, ephemeralKeyPair, consumedOneTimePreKeyId } = x3dhInitiate(
    identityKeyPair,
    remoteBundle
  );
  return {
    identityKeyPair,
    x3dhEphemeral: ephemeralKeyPair,
    ratchet: createRatchetState(sharedSecret),
    remoteSignedPreKey: remoteBundle.signedPreKey,
    consumedOneTimePreKeyId,
  };
}

export function createResponderSession(
  identityKeyPair: X25519KeyPair,
  signedPreKey: X25519KeyPair,
  oneTimePreKey: X25519KeyPair | null
): SignalResponderSession {
  const ratchet = createRatchetState(null);
  ratchet.localSignedPreKey = signedPreKey;
  return { identityKeyPair, signedPreKey, oneTimePreKey, ratchet };
}

export function signalEncrypt(
  session: SignalInitiatorSession,
  plaintext: string | Buffer
): SignalWireMessage {
  const input = typeof plaintext === "string" ? Buffer.from(plaintext, "utf8") : plaintext;
  const wire = ratchetEncrypt(session.ratchet, session.remoteSignedPreKey, input);

  if (session.ratchet.sendMessageNumber === 1) {
    wire.x3dh = {
      identityKey: session.identityKeyPair.publicKey,
      ephemeralKey: session.x3dhEphemeral.publicKey,
    };
  }

  return wire;
}

export function signalDecrypt(
  session: SignalResponderSession,
  message: SignalWireMessage
): Buffer {
  if (message.x3dh) {
    session.ratchet.rootKey = x3dhRespond(
      session.identityKeyPair,
      session.signedPreKey,
      session.oneTimePreKey,
      message.x3dh.identityKey,
      message.x3dh.ephemeralKey
    );
    if (session.oneTimePreKey) session.oneTimePreKey = null;
  }
  return ratchetDecrypt(session.ratchet, message);
}

export function signalDecryptInitiator(
  session: SignalInitiatorSession,
  message: SignalWireMessage
): Buffer {
  return ratchetDecrypt(session.ratchet, message);
}
