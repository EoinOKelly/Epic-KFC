import {
  Direction,
  KeyPairType,
  SessionRecordType,
  StorageType,
} from "@privacyresearch/libsignal-protocol-typescript";

export class InMemoryProtocolStore implements StorageType {
  private identityKeyPair?: KeyPairType;
  private registrationId?: number;
  private readonly preKeys = new Map<string, KeyPairType>();
  private readonly signedPreKeys = new Map<string, KeyPairType>();
  private readonly sessions = new Map<string, SessionRecordType>();
  private readonly identities = new Map<string, ArrayBuffer>();

  constructor(identityKeyPair: KeyPairType, registrationId: number) {
    this.identityKeyPair = identityKeyPair;
    this.registrationId = registrationId;
  }

  async getIdentityKeyPair(): Promise<KeyPairType | undefined> {
    return this.identityKeyPair;
  }

  async getLocalRegistrationId(): Promise<number | undefined> {
    return this.registrationId;
  }

  async isTrustedIdentity(
    identifier: string,
    identityKey: ArrayBuffer,
    _direction: Direction
  ): Promise<boolean> {
    const existing = this.identities.get(identifier);
    if (!existing) return true;
    return buffersEqual(existing, identityKey);
  }

  async saveIdentity(
    encodedAddress: string,
    publicKey: ArrayBuffer,
    _nonblockingApproval?: boolean
  ): Promise<boolean> {
    const existing = this.identities.get(encodedAddress);
    this.identities.set(encodedAddress, publicKey);
    return !existing || !buffersEqual(existing, publicKey);
  }

  async loadPreKey(keyId: number | string): Promise<KeyPairType | undefined> {
    return this.preKeys.get(String(keyId));
  }

  async storePreKey(keyId: number | string, keyPair: KeyPairType): Promise<void> {
    this.preKeys.set(String(keyId), keyPair);
  }

  async removePreKey(keyId: number | string): Promise<void> {
    this.preKeys.delete(String(keyId));
  }

  async storeSession(encodedAddress: string, record: SessionRecordType): Promise<void> {
    this.sessions.set(encodedAddress, record);
  }

  async loadSession(encodedAddress: string): Promise<SessionRecordType | undefined> {
    return this.sessions.get(encodedAddress);
  }

  async loadSignedPreKey(keyId: number | string): Promise<KeyPairType | undefined> {
    return this.signedPreKeys.get(String(keyId));
  }

  async storeSignedPreKey(keyId: number | string, keyPair: KeyPairType): Promise<void> {
    this.signedPreKeys.set(String(keyId), keyPair);
  }

  async removeSignedPreKey(keyId: number | string): Promise<void> {
    this.signedPreKeys.delete(String(keyId));
  }
}

function buffersEqual(a: ArrayBuffer, b: ArrayBuffer): boolean {
  const av = new Uint8Array(a);
  const bv = new Uint8Array(b);
  if (av.length !== bv.length) return false;
  for (let i = 0; i < av.length; i++) if (av[i] !== bv[i]) return false;
  return true;
}
