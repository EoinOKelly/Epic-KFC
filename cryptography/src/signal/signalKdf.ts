import * as crypto from "node:crypto";

export const HKDF_INFO_X3DH = "epic-messaging/v1/signal-x3dh-sk";

export function kdfRootKey(
  rootKey: Buffer,
  dhOutput: Buffer
): { rootKey: Buffer; chainKey: Buffer } {
  const out = Buffer.from(crypto.hkdfSync("sha256", dhOutput, rootKey, Buffer.alloc(0), 64));
  return { rootKey: out.subarray(0, 32), chainKey: out.subarray(32, 64) };
}

export function kdfChainKey(chainKey: Buffer): { chainKey: Buffer; messageKey: Buffer } {
  const messageKey = hmacSha256(chainKey, Buffer.from([0x01]));
  const nextChainKey = hmacSha256(chainKey, Buffer.from([0x02]));
  return { chainKey: nextChainKey, messageKey };
}

export function kdfX3dhSharedSecret(dhOutputs: Buffer[], salt: Buffer): Buffer {
  const ikm = Buffer.concat(dhOutputs);
  return Buffer.from(
    crypto.hkdfSync("sha256", ikm, salt, Buffer.from(HKDF_INFO_X3DH, "utf8"), 32)
  );
}

function hmacSha256(key: Buffer, data: Buffer): Buffer {
  return crypto.createHmac("sha256", key).update(data).digest();
}
