import { decryptMessage, encryptMessage } from "../cryptoEngine";
import { kdfChainKey, kdfRootKey } from "./signalKdf";
import { generateX25519KeyPair, x25519Dh, X25519KeyPair } from "../x25519";

export interface SignalWireMessage {
  ratchetPublicKey?: Buffer;
  counter: number;
  previousCounter: number;
  ciphertext: Buffer;
  iv: Buffer;
  authTag: Buffer;
  x3dh?: { identityKey: Buffer; ephemeralKey: Buffer };
}

export interface DoubleRatchetState {
  rootKey: Buffer | null;
  sendingChainKey: Buffer | null;
  receivingChainKey: Buffer | null;
  sendMessageNumber: number;
  receiveMessageNumber: number;
  previousSendingChainLength: number;
  sendingRatchetKey: X25519KeyPair | null;
  receivingRatchetPublicKey: Buffer | null;
  skippedMessageKeys: Map<string, Buffer>;
  localSignedPreKey?: X25519KeyPair;
}

export function createRatchetState(sharedSecret: Buffer | null): DoubleRatchetState {
  return {
    rootKey: sharedSecret,
    sendingChainKey: null,
    receivingChainKey: null,
    sendMessageNumber: 0,
    receiveMessageNumber: 0,
    previousSendingChainLength: 0,
    sendingRatchetKey: null,
    receivingRatchetPublicKey: null,
    skippedMessageKeys: new Map(),
  };
}

export function ratchetEncrypt(
  state: DoubleRatchetState,
  remoteSignedPreKeyPublic: Buffer,
  plaintext: Buffer
): SignalWireMessage {
  if (!state.rootKey) throw new Error("ratchetEncrypt: session not initialized");

  if (state.sendingChainKey === null) {
    state.sendingRatchetKey = generateX25519KeyPair();
    const derived = kdfRootKey(
      state.rootKey,
      x25519Dh(state.sendingRatchetKey.privateKey, remoteSignedPreKeyPublic)
    );
    state.rootKey = derived.rootKey;
    state.sendingChainKey = derived.chainKey;
    state.sendMessageNumber = 0;
    state.previousSendingChainLength = 0;
  }

  const counter = state.sendMessageNumber;
  const messageKey = nextSendingMessageKey(state);
  const aad = ratchetAad(counter, state.previousSendingChainLength, state.sendingRatchetKey?.publicKey);
  const encrypted = encryptMessage(plaintext, messageKey, aad);

  return {
    ratchetPublicKey: state.sendingRatchetKey?.publicKey,
    counter,
    previousCounter: state.previousSendingChainLength,
    ciphertext: encrypted.ciphertext,
    iv: encrypted.iv,
    authTag: encrypted.authTag,
  };
}

export function ratchetDecrypt(state: DoubleRatchetState, message: SignalWireMessage): Buffer {
  if (!state.rootKey) throw new Error("ratchetDecrypt: session not initialized");

  if (message.ratchetPublicKey) {
    maybeDHRatchet(state, message.ratchetPublicKey);
  }

  const messageKey = getReceivingMessageKey(state, message.counter);
  const aad = ratchetAad(message.counter, message.previousCounter, message.ratchetPublicKey);
  return decryptMessage(message.ciphertext, message.iv, message.authTag, messageKey, aad);
}

function ratchetAad(counter: number, previousCounter: number, ratchetPublicKey?: Buffer): Buffer {
  const header = Buffer.alloc(8);
  header.writeUInt32BE(counter, 0);
  header.writeUInt32BE(previousCounter, 4);
  return ratchetPublicKey ? Buffer.concat([header, ratchetPublicKey]) : header;
}

function maybeDHRatchet(state: DoubleRatchetState, theirPublicKey: Buffer): void {
  if (state.receivingRatchetPublicKey?.equals(theirPublicKey)) return;

  state.previousSendingChainLength = state.sendMessageNumber;
  state.sendMessageNumber = 0;
  state.receivingRatchetPublicKey = theirPublicKey;

  if (state.receivingChainKey === null && state.localSignedPreKey) {
    const derived = kdfRootKey(
      state.rootKey!,
      x25519Dh(state.localSignedPreKey.privateKey, theirPublicKey)
    );
    state.rootKey = derived.rootKey;
    state.receivingChainKey = derived.chainKey;
    state.receiveMessageNumber = 0;
    state.sendingRatchetKey = generateX25519KeyPair();
    return;
  }

  if (!state.sendingRatchetKey) state.sendingRatchetKey = generateX25519KeyPair();

  const recvDerived = kdfRootKey(
    state.rootKey!,
    x25519Dh(state.sendingRatchetKey.privateKey, theirPublicKey)
  );
  state.rootKey = recvDerived.rootKey;
  state.receivingChainKey = recvDerived.chainKey;
  state.receiveMessageNumber = 0;

  const sendDerived = kdfRootKey(
    state.rootKey,
    x25519Dh(state.sendingRatchetKey.privateKey, theirPublicKey)
  );
  state.rootKey = sendDerived.rootKey;
  state.sendingChainKey = sendDerived.chainKey;
  state.sendMessageNumber = 0;
  state.sendingRatchetKey = generateX25519KeyPair();
}

function nextSendingMessageKey(state: DoubleRatchetState): Buffer {
  if (!state.sendingChainKey) throw new Error("ratchetEncrypt: no sending chain");
  const { chainKey, messageKey } = kdfChainKey(state.sendingChainKey);
  state.sendingChainKey = chainKey;
  state.sendMessageNumber += 1;
  return messageKey;
}

function getReceivingMessageKey(state: DoubleRatchetState, counter: number): Buffer {
  if (!state.receivingChainKey || !state.receivingRatchetPublicKey) {
    throw new Error("ratchetDecrypt: no receiving chain");
  }

  const skipId = (n: number) =>
    `${state.receivingRatchetPublicKey!.toString("base64")}:${n}`;

  const cached = state.skippedMessageKeys.get(skipId(counter));
  if (cached) {
    state.skippedMessageKeys.delete(skipId(counter));
    return cached;
  }

  while (state.receiveMessageNumber <= counter) {
    const { chainKey, messageKey } = kdfChainKey(state.receivingChainKey);
    state.receivingChainKey = chainKey;

    if (state.receiveMessageNumber < counter) {
      state.skippedMessageKeys.set(skipId(state.receiveMessageNumber), messageKey);
    } else {
      return messageKey;
    }
    state.receiveMessageNumber += 1;
  }

  throw new Error("ratchetDecrypt: missing message key");
}
