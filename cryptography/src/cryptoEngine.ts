import * as crypto from "node:crypto";
import * as argon2 from "argon2";
import { generateEd25519KeyPair } from "./ed25519";
import { generateX25519KeyPair } from "./x25519";

const AES_KEY_BYTES = 32;
const GCM_IV_BYTES = 12;
const ARGON2_SALT_BYTES = 16;
const AT_REST_BLOB_VERSION = 1;

const ARGON2_OPTIONS: argon2.Options & { type: typeof argon2.argon2id } = {
  type: argon2.argon2id,
  memoryCost: 65536,
  timeCost: 3,
  parallelism: 4,
  hashLength: AES_KEY_BYTES,
};

export const HKDF_INFO_LOCAL_STORAGE = "epic-messaging/v1/local-storage-key";
export const HKDF_INFO_SESSION = "epic-messaging/v1/session-key";

export const CRYPTO_ALGORITHMS = {
  passwordHash: "argon2id",
  kdf: "HKDF-SHA256",
  messageAead: "AES-256-GCM",
  kem: "X25519",
  auth: "Ed25519",
} as const;

export interface PasswordHashResult {
  /** PHC-encoded Argon2id string — this is the only column required for login. */
  hash: string;
  /** Duplicate of salt embedded in `hash`; optional separate DB column. */
  salt: string;
}

export interface DerivedKeys {
  localStorageKey: Buffer;
  sessionKey: Buffer;
}

export interface EncryptedMessage {
  ciphertext: Buffer;
  iv: Buffer;
  authTag: Buffer;
}

export interface HpkeOrientedKeyPair {
  kem: { publicKey: Buffer; privateKey: Buffer };
  auth: { publicKey: Buffer; privateKey: Buffer };
}

export interface EncryptedPrivateKeyBlob {
  version: number;
  iv: Buffer;
  authTag: Buffer;
  ciphertext: Buffer;
}

export async function hashPassword(password: string): Promise<PasswordHashResult> {
  if (!password) throw new Error("hashPassword: password must not be empty");

  const salt = crypto.randomBytes(ARGON2_SALT_BYTES);
  const hash = await argon2.hash(password, { ...ARGON2_OPTIONS, salt });

  return { hash, salt: salt.toString("base64") };
}

export async function verifyPassword(password: string, storedHash: string): Promise<boolean> {
  try {
    return await argon2.verify(storedHash, password);
  } catch {
    return false;
  }
}

export function deriveKeys(masterKey: Buffer, salt: Buffer): DerivedKeys {
  if (masterKey.length < 16) throw new Error("deriveKeys: masterKey too short");
  if (salt.length < 8) throw new Error("deriveKeys: salt too short");

  return {
    localStorageKey: hkdfExpand(masterKey, salt, HKDF_INFO_LOCAL_STORAGE, AES_KEY_BYTES),
    sessionKey: hkdfExpand(masterKey, salt, HKDF_INFO_SESSION, AES_KEY_BYTES),
  };
}

export function encryptMessage(
  plaintext: string | Buffer,
  symmetricKey: Buffer,
  associatedData?: Buffer
): EncryptedMessage {
  assertAesKey(symmetricKey);

  const iv = crypto.randomBytes(GCM_IV_BYTES);
  const cipher = crypto.createCipheriv("aes-256-gcm", symmetricKey, iv);
  if (associatedData?.length) cipher.setAAD(associatedData);

  const input = typeof plaintext === "string" ? Buffer.from(plaintext, "utf8") : plaintext;
  const ciphertext = Buffer.concat([cipher.update(input), cipher.final()]);

  return { ciphertext, iv, authTag: cipher.getAuthTag() };
}

export function decryptMessage(
  ciphertext: Buffer,
  iv: Buffer,
  authTag: Buffer,
  symmetricKey: Buffer,
  associatedData?: Buffer
): Buffer {
  assertAesKey(symmetricKey);
  if (iv.length !== GCM_IV_BYTES) throw new Error(`decryptMessage: IV must be ${GCM_IV_BYTES} bytes`);
  if (authTag.length !== 16) throw new Error("decryptMessage: auth tag must be 16 bytes");

  const decipher = crypto.createDecipheriv("aes-256-gcm", symmetricKey, iv);
  if (associatedData?.length) decipher.setAAD(associatedData);
  decipher.setAuthTag(authTag);

  try {
    return Buffer.concat([decipher.update(ciphertext), decipher.final()]);
  } catch {
    throw new Error("decryptMessage: authentication failed");
  }
}

export function generateKeyPair(): HpkeOrientedKeyPair {
  const kem = generateX25519KeyPair();
  const auth = generateEd25519KeyPair();
  return { kem, auth };
}

export function encryptPrivateKeyForStorage(
  privateKey: Buffer,
  storageKey: Buffer
): EncryptedPrivateKeyBlob {
  assertAesKey(storageKey);

  const iv = crypto.randomBytes(GCM_IV_BYTES);
  const cipher = crypto.createCipheriv("aes-256-gcm", storageKey, iv);
  const ciphertext = Buffer.concat([cipher.update(privateKey), cipher.final()]);

  return {
    version: AT_REST_BLOB_VERSION,
    iv,
    authTag: cipher.getAuthTag(),
    ciphertext,
  };
}

export function decryptPrivateKeyFromStorage(
  blob: EncryptedPrivateKeyBlob,
  storageKey: Buffer
): Buffer {
  assertAesKey(storageKey);
  if (blob.version !== AT_REST_BLOB_VERSION) {
    throw new Error(`decryptPrivateKeyFromStorage: unsupported version ${blob.version}`);
  }
  return decryptMessage(blob.ciphertext, blob.iv, blob.authTag, storageKey);
}

function hkdfExpand(ikm: Buffer, salt: Buffer, info: string, length: number): Buffer {
  return Buffer.from(crypto.hkdfSync("sha256", ikm, salt, Buffer.from(info, "utf8"), length));
}

function assertAesKey(key: Buffer): void {
  if (key.length !== AES_KEY_BYTES) {
    throw new Error(`Symmetric key must be ${AES_KEY_BYTES} bytes`);
  }
}
