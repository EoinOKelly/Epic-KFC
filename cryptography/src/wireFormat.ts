import { fromBase64, toBase64 } from "./bufferUtils";
import { SignalWireMessage } from "./signal/doubleRatchet";

/** JSON-safe form for DB / HTTP. Binary fields are base64. */
export interface StoredWireMessage {
  ratchetPublicKey?: string;
  counter: number;
  previousCounter: number;
  ciphertext: string;
  iv: string;
  authTag: string;
  x3dh?: { identityKey: string; ephemeralKey: string };
}

export function serializeWireMessage(msg: SignalWireMessage): string {
  const stored: StoredWireMessage = {
    counter: msg.counter,
    previousCounter: msg.previousCounter,
    ciphertext: toBase64(msg.ciphertext),
    iv: toBase64(msg.iv),
    authTag: toBase64(msg.authTag),
  };
  if (msg.ratchetPublicKey) stored.ratchetPublicKey = toBase64(msg.ratchetPublicKey);
  if (msg.x3dh) {
    stored.x3dh = {
      identityKey: toBase64(msg.x3dh.identityKey),
      ephemeralKey: toBase64(msg.x3dh.ephemeralKey),
    };
  }
  return JSON.stringify(stored);
}

export function deserializeWireMessage(json: string): SignalWireMessage {
  const stored = JSON.parse(json) as StoredWireMessage;
  const msg: SignalWireMessage = {
    counter: stored.counter,
    previousCounter: stored.previousCounter,
    ciphertext: fromBase64(stored.ciphertext),
    iv: fromBase64(stored.iv),
    authTag: fromBase64(stored.authTag),
  };
  if (stored.ratchetPublicKey) msg.ratchetPublicKey = fromBase64(stored.ratchetPublicKey);
  if (stored.x3dh) {
    msg.x3dh = {
      identityKey: fromBase64(stored.x3dh.identityKey),
      ephemeralKey: fromBase64(stored.x3dh.ephemeralKey),
    };
  }
  return msg;
}
