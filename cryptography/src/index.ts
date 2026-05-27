/**
 * @epic-messaging/cryptography — public API
 *
 * Import from the built package or, during development:
 *   import { hashPassword, encryptMessage, ... } from '@epic-messaging/cryptography';
 */

export {
  CRYPTO_ALGORITHMS,
  HKDF_INFO_LOCAL_STORAGE,
  HKDF_INFO_SESSION,
  hashPassword,
  verifyPassword,
  deriveKeys,
  encryptMessage,
  decryptMessage,
  generateKeyPair,
  encryptPrivateKeyForStorage,
  decryptPrivateKeyFromStorage,
} from "./cryptoEngine";

export type {
  PasswordHashResult,
  DerivedKeys,
  EncryptedMessage,
  HpkeOrientedKeyPair,
  EncryptedPrivateKeyBlob,
} from "./cryptoEngine";
