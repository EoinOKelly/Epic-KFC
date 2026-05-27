/**
 * Epic Messaging — Cryptography Engine
 *
 * Standalone utilities for password hashing, key derivation, AEAD messaging,
 * HPKE-oriented key generation, and private-key protection at rest.
 *
 * Design constraints (see project .cursorrules):
 * - AEAD only for payloads (AES-256-GCM here; ChaCha20-Poly1305 is also permitted)
 * - HKDF with explicit salt and info labels
 * - Argon2id for passwords
 * - X25519 + Ed25519 key material aligned with HPKE Mode_Auth (RFC 9180) and TOFU pinning
 * - Local private keys encrypted with a separately derived storage sub-key
 */

import * as crypto from "node:crypto";
import * as argon2 from "argon2";

// ---------------------------------------------------------------------------
// Constants — documented for the cryptographic design report
// ---------------------------------------------------------------------------

/** AES-256 key size in bytes (256-bit keys for AES-256-GCM). */
const AES_KEY_BYTES = 32;

/**
 * GCM nonce (IV) length: 96 bits (12 bytes).
 * NIST SP 800-38D recommends 96-bit IVs for GCM; shorter/longer IVs work but
 * require different GHASH handling. 12 bytes is the conventional choice and
 * keeps wire format compact while remaining unique per key under random generation.
 */
const GCM_IV_BYTES = 12;

/**
 * Argon2id parameters (OWASP Password Storage Cheat Sheet, 2023+).
 *
 * - type: argon2id — hybrid of Argon2i (side-channel resistant) and Argon2d
 *   (GPU-hard). Argon2id is the recommended variant for password hashing.
 * - memoryCost: 65536 KiB = 64 MiB — raises cost of parallel ASIC/GPU attacks
 *   by bounding memory bandwidth; aligns with OWASP “strong” interactive tier.
 * - timeCost: 3 iterations — increases CPU time linearly; tune upward if
 *   registration/login latency budget allows (measure on target hardware).
 * - parallelism: 4 lanes — uses multiple cores without multiplying memory cost
 *   per lane (unlike scrypt). Match to available CPU cores on the server.
 * - hashLength: 32 bytes — output size; 256 bits is sufficient for verifier storage.
 * - saltLength: 16 bytes (128 bits) — standard random salt size; uniqueness
 *   across users defeats rainbow tables.
 */
const ARGON2_OPTIONS: argon2.Options & { type: typeof argon2.argon2id } = {
  type: argon2.argon2id,
  memoryCost: 65536,
  timeCost: 3,
  parallelism: 4,
  hashLength: AES_KEY_BYTES,
};

const ARGON2_SALT_BYTES = 16;

/**
 * HKDF info strings — domain separation labels (RFC 5869).
 * Distinct info values ensure the same IKM + salt cannot produce interchangeable
 * key material across contexts (storage vs session vs future extensions).
 */
export const HKDF_INFO_LOCAL_STORAGE = "epic-messaging/v1/local-storage-key";
export const HKDF_INFO_SESSION = "epic-messaging/v1/session-key";

/** Algorithm identifiers exported for integrators and design documentation. */
export const CRYPTO_ALGORITHMS = {
  passwordHash: "argon2id",
  kdf: "HKDF-SHA256",
  messageAead: "AES-256-GCM",
  atRestAead: "AES-256-GCM",
  kem: "X25519",
  auth: "Ed25519",
} as const;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface PasswordHashResult {
  /** PHC-string encoded hash (includes embedded parameters); pass to verifyPassword. */
  hash: string;
  /** Random salt used for this hash, Base64-encoded (also embedded in `hash`). */
  salt: string;
}

export interface DerivedKeys {
  /** 32-byte key for encrypting private keys and other long-lived local secrets. */
  localStorageKey: Buffer;
  /** 32-byte key for ephemeral session/message-layer use (integrators map as needed). */
  sessionKey: Buffer;
}

export interface EncryptedMessage {
  /** Ciphertext without IV or tag (raw AES-GCM output). */
  ciphertext: Buffer;
  /** 12-byte GCM nonce — must be stored/transmitted with the ciphertext. */
  iv: Buffer;
  /** 16-byte GCM authentication tag — AEAD integrity; reject if missing/wrong. */
  authTag: Buffer;
}

/**
 * Key bundle for HPKE Mode_Auth-style setups and TOFU public-key pinning.
 *
 * - kem: X25519 (DHKEM per RFC 9180) for Diffie–Hellman encapsulation
 * - auth: Ed25519 for sender authentication in HPKE base mode "auth"
 *
 * Teammates performing full HPKE should use a dedicated HPKE library with these
 * raw keys; this module only generates and protects key material.
 */
export interface HpkeOrientedKeyPair {
  kem: {
    publicKey: Buffer;
    privateKey: Buffer;
  };
  auth: {
    publicKey: Buffer;
    privateKey: Buffer;
  };
}

export interface EncryptedPrivateKeyBlob {
  /** Format version for future algorithm agility. */
  version: number;
  iv: Buffer;
  authTag: Buffer;
  ciphertext: Buffer;
}

// ---------------------------------------------------------------------------
// 1. Password hashing (Argon2id)
// ---------------------------------------------------------------------------

/**
 * Hashes a user password with Argon2id.
 *
 * @param password - UTF-8 string from registration UI (never log or persist plaintext).
 * @returns Encoded hash (PHC format) and separate Base64 salt for DB/schema flexibility.
 *
 * Store `hash` for verification; `salt` is also inside `hash` but returned separately
 * so backends can index or display salt in design demos if required.
 */
export async function hashPassword(password: string): Promise<PasswordHashResult> {
  if (!password || password.length === 0) {
    throw new Error("hashPassword: password must not be empty");
  }

  const salt = crypto.randomBytes(ARGON2_SALT_BYTES);

  const hash = await argon2.hash(password, {
    ...ARGON2_OPTIONS,
    salt,
  });

  return {
    hash,
    salt: salt.toString("base64"),
  };
}

/**
 * Verifies a password against a stored Argon2id PHC hash.
 * Convenience for backend teams; not in the original API list but required for integration.
 */
export async function verifyPassword(password: string, storedHash: string): Promise<boolean> {
  try {
    return await argon2.verify(storedHash, password);
  } catch {
    return false;
  }
}

// ---------------------------------------------------------------------------
// 2. HKDF key derivation
// ---------------------------------------------------------------------------

/**
 * Derives two independent 256-bit sub-keys from a master secret using HKDF-SHA256.
 *
 * Uses Node's `crypto.hkdfSync` (RFC 5869) with:
 * - explicit `salt` (should be unique per user or per derivation context)
 * - distinct `info` labels per sub-key so storage and session keys are unrelated
 *
 * Typical flow: masterKey comes from Argon2id(password) or another strong KDF output;
 * never use the raw password as IKM after registration.
 *
 * @param masterKey - Input keying material (IKM), e.g. 32 bytes from password hash output.
 * @param salt - Salt for HKDF Extract step (can be application/user-specific).
 */
export function deriveKeys(masterKey: Buffer, salt: Buffer): DerivedKeys {
  if (masterKey.length < 16) {
    throw new Error("deriveKeys: masterKey should be at least 128 bits");
  }
  if (salt.length < 8) {
    throw new Error("deriveKeys: salt should be at least 64 bits");
  }

  const localStorageKey = hkdfExpand(masterKey, salt, HKDF_INFO_LOCAL_STORAGE, AES_KEY_BYTES);
  const sessionKey = hkdfExpand(masterKey, salt, HKDF_INFO_SESSION, AES_KEY_BYTES);

  return { localStorageKey, sessionKey };
}

function hkdfExpand(
  ikm: Buffer,
  salt: Buffer,
  info: string,
  length: number
): Buffer {
  return Buffer.from(
    crypto.hkdfSync("sha256", ikm, salt, Buffer.from(info, "utf8"), length)
  );
}

// ---------------------------------------------------------------------------
// 3–4. Message encryption / decryption (AES-256-GCM AEAD)
// ---------------------------------------------------------------------------

/**
 * Encrypts a message with AES-256-GCM (authenticated encryption with associated data).
 *
 * Why AES-256-GCM (and not encrypt-then-MAC):
 * - GCM provides confidentiality and integrity in one primitive (AEAD), avoiding
 *   fragile compose-your-own schemes that have historically led to vulnerabilities.
 * - Hardware acceleration (AES-NI + CLMUL) is widely available on servers and laptops.
 * - 256-bit keys provide a comfortable margin against future Grover-style attacks on
 *   symmetric primitives in academic threat models.
 *
 * A fresh random IV is generated per message. Never reuse an IV under the same key.
 *
 * @param plaintext - Message bytes or UTF-8 string.
 * @param symmetricKey - Exactly 32 bytes (use `deriveKeys().sessionKey` or HPKE export).
 */
export function encryptMessage(
  plaintext: string | Buffer,
  symmetricKey: Buffer
): EncryptedMessage {
  assertAesKey(symmetricKey);

  const iv = crypto.randomBytes(GCM_IV_BYTES);
  const cipher = crypto.createCipheriv("aes-256-gcm", symmetricKey, iv);

  const input = typeof plaintext === "string" ? Buffer.from(plaintext, "utf8") : plaintext;
  const ciphertext = Buffer.concat([cipher.update(input), cipher.final()]);
  const authTag = cipher.getAuthTag();

  return { ciphertext, iv, authTag };
}

/**
 * Decrypts an AES-256-GCM message. Throws if authentication fails (tampered or wrong key).
 *
 * @param ciphertext - Output from encryptMessage (no IV/tag prefixed).
 * @param iv - 12-byte nonce from encryptMessage.
 * @param authTag - 16-byte GCM tag from encryptMessage.
 * @param symmetricKey - Same 32-byte key used for encryption.
 */
export function decryptMessage(
  ciphertext: Buffer,
  iv: Buffer,
  authTag: Buffer,
  symmetricKey: Buffer
): Buffer {
  assertAesKey(symmetricKey);

  if (iv.length !== GCM_IV_BYTES) {
    throw new Error(`decryptMessage: IV must be ${GCM_IV_BYTES} bytes`);
  }
  if (authTag.length !== 16) {
    throw new Error("decryptMessage: auth tag must be 16 bytes");
  }

  const decipher = crypto.createDecipheriv("aes-256-gcm", symmetricKey, iv);
  decipher.setAuthTag(authTag);

  try {
    return Buffer.concat([decipher.update(ciphertext), decipher.final()]);
  } catch {
    throw new Error("decryptMessage: authentication failed or invalid ciphertext");
  }
}

// ---------------------------------------------------------------------------
// 5. Asymmetric key generation (HPKE / TOFU)
// ---------------------------------------------------------------------------

/**
 * Generates an X25519 KEM key pair and an Ed25519 authentication key pair.
 *
 * HPKE (RFC 9180) Mode_Auth combines:
 * - DHKEM(X25519, HKDF-SHA256) for shared secret establishment
 * - Digital signature (here Ed25519) so recipients can pin/authenticate senders
 *
 * TOFU integration: on first contact, persist `kem.publicKey` and `auth.publicKey`;
 * reject messages if later keys do not match (see tofu.ts / backend trust store).
 *
 * Keys are raw 32-byte buffers for easy passing to HPKE libraries or C++ via FFI.
 */
export function generateKeyPair(): HpkeOrientedKeyPair {
  const kem = generateX25519KeyPair();
  const authPrivate = crypto.randomBytes(32);
  const authPublic = ed25519PublicFromPrivate(authPrivate);

  return {
    kem,
    auth: { publicKey: authPublic, privateKey: authPrivate },
  };
}

/**
 * X25519 key pair via Node WebCrypto-style key objects (RFC 7748).
 * Raw 32-byte keys are extracted from JWK for HPKE library interoperability.
 */
function generateX25519KeyPair(): { publicKey: Buffer; privateKey: Buffer } {
  const { publicKey, privateKey } = crypto.generateKeyPairSync("x25519");

  const privJwk = privateKey.export({ format: "jwk" }) as { d?: string };
  const pubJwk = publicKey.export({ format: "jwk" }) as { x?: string };

  if (!privJwk.d || !pubJwk.x) {
    throw new Error("generateX25519KeyPair: failed to export raw X25519 material");
  }

  return {
    privateKey: Buffer.from(privJwk.d, "base64url"),
    publicKey: Buffer.from(pubJwk.x, "base64url"),
  };
}

/**
 * Ed25519 public key from a 32-byte private seed.
 * Node derives the public key from PKCS#8-wrapped seed material (RFC 8410).
 */
function ed25519PublicFromPrivate(seed: Buffer): Buffer {
  const privateKeyObject = crypto.createPrivateKey({
    key: wrapEd25519SeedAsPkcs8(seed),
    format: "der",
    type: "pkcs8",
  });
  const publicKeyObject = crypto.createPublicKey(privateKeyObject);
  const spki = publicKeyObject.export({ type: "spki", format: "der" }) as Buffer;
  // Ed25519 SPKI DER: raw 32-byte public key is the final octet string
  return spki.subarray(-32);
}

/** Minimal PKCS#8 wrapper for a 32-byte Ed25519 seed (RFC 8410). */
function wrapEd25519SeedAsPkcs8(seed: Buffer): Buffer {
  const prefix = Buffer.from("302e020100300506032b657004220420", "hex");
  return Buffer.concat([prefix, seed]);
}

// ---------------------------------------------------------------------------
// 6. Private key encryption at rest
// ---------------------------------------------------------------------------

const AT_REST_BLOB_VERSION = 1;

/**
 * Encrypts a private key (or any sensitive blob) for local persistence.
 *
 * Uses AES-256-GCM with `storageKey` from `deriveKeys().localStorageKey` — never
 * the session key or raw password. This satisfies the requirement that local private
 * keys are encrypted with a separately derived sub-key.
 *
 * @param privateKey - Raw private key bytes (e.g. kem.privateKey or auth.privateKey).
 * @param storageKey - 32-byte `localStorageKey` from deriveKeys().
 */
export function encryptPrivateKeyForStorage(
  privateKey: Buffer,
  storageKey: Buffer
): EncryptedPrivateKeyBlob {
  assertAesKey(storageKey);

  const iv = crypto.randomBytes(GCM_IV_BYTES);
  const cipher = crypto.createCipheriv("aes-256-gcm", storageKey, iv);
  const ciphertext = Buffer.concat([cipher.update(privateKey), cipher.final()]);
  const authTag = cipher.getAuthTag();

  return {
    version: AT_REST_BLOB_VERSION,
    iv,
    authTag,
    ciphertext,
  };
}

/**
 * Decrypts a blob produced by encryptPrivateKeyForStorage.
 */
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

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function assertAesKey(key: Buffer): void {
  if (key.length !== AES_KEY_BYTES) {
    throw new Error(`Symmetric key must be ${AES_KEY_BYTES} bytes for AES-256-GCM`);
  }
}
